"""Interpreter and planner: one LLM call per turn, outside the executor's history."""

import fnmatch
import json
import re

PROMPT = """You plan one turn of an operations agent. You do not execute anything.

Conversation so far:
{history}

Known aliases for this session: {aliases}

Current system state:
{state}

Available tools, with required parameters (other tools do not exist):
{tools}

Current user request:
{request}

Return one JSON object and nothing else:
{{
 "clarify": null or a question,
 "summary": ["at most three short lines saying what will happen"],
 "aliases": {{"phrase the user used": "concrete path or id it refers to"}},
 "readings": {{"group phrase the user used": [["items for one reading"], ["items for another"]]}},
 "groups": [{{"phrase": "group phrase", "folder": "/absolute/folder/holding/them",
             "pattern": "shell-style name pattern", "action": "move, copy or delete",
             "destination": "/absolute/destination/folder or null"}}],
 "effects": [ expected end-of-turn effects ]
}}

When the request refers to items by a description rather than by name ("the March runs"), add a
"groups" entry: the folder that holds them and a name pattern (such as run_03*) that matches every
intended item in that folder and nothing else. Steward checks every item the pattern matches.

Set "clarify" to a short question, and change nothing, in any of these cases:
1. A value that a tool strictly requires appears nowhere in the request, the conversation, earlier
   tool results or the state, and could not be found by a read tool, so you would have to invent it.
2. The request describes a group of items vaguely ("the old runs", "the big files", "those",
   "the rest") and more than one different set of items in the state fits the description. List each
   plausible set under "readings" and ask which one is meant, naming the candidates.
3. The request seems to take back or contradict a change already made in this conversation
   ("actually, nothing else should move" after a move). Ask whether to keep or undo that change.
4. Part of the request needs an action that no available tool performs. Do not substitute a
   different tool or do only the rest: say which part cannot be done with the available tools.
For rule 1, check each required parameter of each tool you would call. A value counts as known
if it is stated, appears in the state or earlier results, or a read tool can look it up. When the
state or earlier results hold exactly one clear match for what the user named (a company and its
stock symbol, a person and their user id), use it; do not ask the user to confirm it.
Do not ask when the request can be carried out as written. A clear description such as "the March
runs" when item names carry dates, or a mistyped name that clearly matches one item, is not a reason
to ask. For every group phrase, give "readings" with one entry per plausible set, even if only one.

When the request refers to a group of items, go through the whole file tree and include every
item that matches, naming each one in "aliases" and in the effects.

Allowed effects, using only what the user explicitly asked to change:
 {{"type": "exists", "path": "name or path"}}
 {{"type": "absent", "path": "name or path"}}
 {{"type": "content_contains", "path": "file", "text": "exact text the user supplied"}}
 {{"type": "ticket_status", "ticket_id": 1, "status": "Closed"}}
 {{"type": "ticket_exists", "title": "exact title"}}
 {{"type": "message_sent", "text": "a phrase the message must contain"}}

Use an empty effects list for read-only requests, and for anything these types cannot express.
Never use placeholders or values that must be computed first; leave such effects out.
Do not list a source file as absent after a copy. Do not invent effects the user did not ask for.
"""

FALLBACK = {"clarify": None, "summary": [], "aliases": {}, "readings": {}, "groups": [], "effects": []}


def parse_plan(text):
    """Extract the JSON object from a model reply; a bad reply means no plan, not a crash."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return dict(FALLBACK, error="no JSON in planner reply")
    try:
        data = json.loads(match.group(0))
    except ValueError as exc:
        return dict(FALLBACK, error=f"bad JSON from planner: {exc}")
    effects = data.get("effects")
    return {
        "clarify": data.get("clarify") or None,
        "summary": [str(s) for s in (data.get("summary") or [])][:3],
        "aliases": data.get("aliases") if isinstance(data.get("aliases"), dict) else {},
        "readings": _readings(data.get("readings")),
        "groups": [g for g in data.get("groups") or [] if isinstance(g, dict)]
        if isinstance(data.get("groups"), list) else [],
        "effects": [e for e in effects if isinstance(e, dict)] if isinstance(effects, list) else [],
    }


def _readings(raw):
    """Keep {phrase: [[item, ...], ...]} with each reading as a sorted, de-duplicated list."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for phrase, options in raw.items():
        if not isinstance(options, list):
            continue
        sets = []
        for option in options:
            items = option if isinstance(option, list) else [option]
            items = sorted({str(i).rstrip("/") for i in items if str(i).strip()})
            if items and items not in sets:
                sets.append(items)
        if sets:
            out[str(phrase)] = sets
    return out


VAGUE = re.compile(
    r"\b(old|older|oldest|recent|latest|stale|unused|temporary|temp|big|bigger|biggest|large|"
    r"larger|largest|small|smaller|junk|misc|leftover|leftovers|useless|unneeded|unnecessary|stuff)\b",
    re.I)
SPECIFIC = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|june?|july?|aug(ust)?|sep(t(ember)?)?|"
    r"oct(ober)?|nov(ember)?|dec(ember)?)\b|\d{2,}", re.I)


def _short(item):
    return str(item).rstrip("/").rsplit("/", 1)[-1]


def _files_only(sets, fs_names):
    """True when every item in every reading is an existing file or folder."""
    return bool(fs_names) and all(_short(i) in fs_names for s in sets for i in s)


def ambiguity(plan, request, fs_names=()):
    """Return a question when a group of files has several readings, else None. Deterministic.

    Two checks: the planner's own readings disagree, or a vague phrase ("the old runs") was
    resolved to several items although the request gives no date, number, name or "all".
    Both apply only to groups of existing files and folders; for other tools (a car's settings,
    a stock order) the planner's readings are not items to choose between, so it decides itself.
    """
    fs_names = set(fs_names)
    for phrase, sets in plan.get("readings", {}).items():
        if len(sets) > 1 and _files_only(sets, fs_names):
            options = "; or ".join(", ".join(_short(i) for i in s) for s in sets[:4])
            return f'When you say "{phrase}", which do you mean: {options}? Nothing has been changed yet.'
    if not plan.get("effects"):
        return None
    vague_request = VAGUE.search(request) and not SPECIFIC.search(request)
    for phrase, sets in plan.get("readings", {}).items():
        if vague_request and len(sets) == 1 and len(sets[0]) > 1 and VAGUE.search(str(phrase)) \
                and _files_only(sets, fs_names):
            names = ", ".join(_short(i) for i in sets[0][:8])
            return (f'"{phrase}" could cover several items: {names}. Which of these should I include? '
                    "Nothing has been changed yet.")
    for phrase, target in plan.get("aliases", {}).items():
        items = [t for t in re.split(r"[,;]\s*", str(target)) if t.strip()]
        if len(items) > 1 and VAGUE.search(str(phrase)) and VAGUE.search(request) \
                and not SPECIFIC.search(request) and _files_only([items], fs_names):
            names = ", ".join(_short(i) for i in items[:8])
            return (f'"{phrase}" could mean several different sets of items. I found {names}. '
                    f"Which of these should I include? Nothing has been changed yet.")
    return None


def signature(function):
    """One line per tool: name(required, [optional]) - short description."""
    params = function.get("parameters", {}) or {}
    required = params.get("required", []) or []
    optional = [p for p in (params.get("properties") or {}) if p not in required]
    desc = str(function.get("description", ""))
    desc = desc.split("Tool description:", 1)[-1].strip().split(". ")[0][:90]
    args = ", ".join(required + [f"[{p}]" for p in optional])
    return f"{function.get('name')}({args}) - {desc}"


def plan_prompt(history, aliases, state, tools, request):
    tools = "\n".join(t if isinstance(t, str) else signature(t) for t in tools)
    return PROMPT.format(
        history="\n".join(f"- {h}" for h in history) or "(none)",
        aliases=json.dumps(aliases), state=state, tools=tools, request=request,
    )


def irreversible(plan):
    """Moves in the plan that the tools cannot undo: an item leaving its folder for another one.

    The file tools cannot name a parent folder as a destination, so such a move has no inverse.
    """
    gone = {str(e.get("path", "")).rstrip("/") for e in plan.get("effects", []) if e.get("type") == "absent"}
    moves = []
    for effect in plan.get("effects", []):
        if effect.get("type") != "exists":
            continue
        new = str(effect.get("path", "")).rstrip("/")
        name = new.rsplit("/", 1)[-1]
        for old in gone:
            if old.rsplit("/", 1)[-1] == name and old.rsplit("/", 1)[0] != new.rsplit("/", 1)[0]:
                moves.append(f"{old} -> {new.rsplit('/', 1)[0]}/")
    return sorted(moves)


ACTIONS = {"move", "copy", "delete"}


def expand_groups(plan, fs):
    """Turn each group's folder and pattern into the full item list and one effect per item.

    The item list comes from the probed state, not from the planner's memory of it, so an item the
    planner left out of its own list is still expected and checked. Adds plan["items"].
    """
    effects, items = list(plan.get("effects", [])), {}
    for group in plan.get("groups", []):
        folder = "/" + str(group.get("folder", "")).strip("/")
        pattern = str(group.get("pattern", "")).strip()
        action = str(group.get("action", "")).lower()
        if not pattern or pattern in ("*", "*.*") or action not in ACTIONS:
            continue
        names = sorted(p.rsplit("/", 1)[-1] for p in fs
                       if p.rsplit("/", 1)[0] == folder and fnmatch.fnmatchcase(p.rsplit("/", 1)[-1], pattern))
        if not names:
            continue
        dest = "/" + str(group.get("destination") or "").strip("/")
        if action in ("move", "copy") and dest == "/":
            continue
        items[str(group.get("phrase") or pattern)] = names
        for name in names:
            new = []
            if action in ("move", "delete"):
                new.append({"type": "absent", "path": f"{folder}/{name}"})
            if action in ("move", "copy"):
                new.append({"type": "exists", "path": f"{dest}/{name}"})
            effects += [e for e in new if e not in effects]
    plan["effects"], plan["items"] = effects, items
    return plan


# Deterministic ask rules. Each returns a question or None and runs before anything executes.

WORD = re.compile(r"(?<![\w.'\"])[A-Za-z]{5,}(?![\w.'\"])")


def _distance(a, b, limit=2):
    """Levenshtein distance, stopping early once it exceeds the limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        best = i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
            best = min(best, row[j])
        if best > limit:
            return limit + 1
    return row[-1]


def near_miss(request, fs_names, known_text=""):
    """A plain word in the request that names no item but is one typo away from an existing one.

    "Go to the scrach folder" when only "scratch" exists: the user should confirm which item they
    mean rather than have it guessed. Only plain alphabetic words and names are compared, so new
    names the user is creating (file5.txt, report_2.md) never count, and neither do plurals, case,
    words already used earlier in the conversation, or words that are real items.
    """
    names = {n.lower(): n for n in fs_names if n.isalpha() and len(n) >= 5}
    if not names:
        return None
    known = known_text.lower()
    for word in WORD.findall(request):
        low = word.lower()
        if low in names or re.search(rf"\b{low}\b", known):
            continue
        for name_low, name in names.items():
            if low.rstrip("s") == name_low.rstrip("s") or low in name_low or name_low in low:
                continue
            limit = 1 if len(name_low) < 8 else 2
            if _distance(low, name_low, limit) <= limit:
                return (f'I could not find "{word}". Did you mean "{name}"? '
                        "Nothing has been changed yet.")
    return None


REVERSAL = re.compile(
    r"\b(nothing else should|no other (file|folder|item|change)s? should|"
    r"(don't|do not) (move|change|touch|delete) anything else)\b", re.I)


def reversal(request, previous_changes):
    """The user seems to take back or narrow what was just done, after something was changed.

    Steward then asks whether to keep or undo the earlier change before doing anything new.
    """
    if not previous_changes or not REVERSAL.search(request):
        return None
    shown = "; ".join(previous_changes[:4])
    return ("Before I go on: the last request already changed things "
            f"({shown}). Should I keep that change or undo it? Nothing has been changed yet.")


REVIEW = """You check whether an operations agent finished one user request. You do not act.

Conversation before this request:
{history}

User request:
{request}

What the agent did for this request (calls and results, in order):
{trace}

The agent's last words to the user:
{reply}

Current system state:
{state}

Return one JSON object and nothing else:
{{"done": true}} when every part of the request was carried out, or the agent clearly told the
user that a part cannot be done or asked the user a question about it;
{{"done": false, "missing": "the specific part of the request that is not done"}} otherwise.
Judge only from the calls, results and state above. For a question, the answer must be based on
results the agent actually read. Never require work the user did not ask for.
"""


def review_prompt(history, request, trace, reply, state):
    return REVIEW.format(history="\n".join(f"- {h}" for h in history[-8:]) or "(none)",
                         request=request, trace="\n".join(trace)[-2500:] or "(no calls)",
                         reply=str(reply)[:600] or "(none)", state=state)


def parse_review(text):
    """{"done": bool, "missing": str}; an unreadable reply counts as done so it never forces work."""
    match = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    done = data.get("done", True) is not False
    return {"done": done, "missing": "" if done else str(data.get("missing") or "part of the request")[:300]}
