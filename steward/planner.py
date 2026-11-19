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

Available tools: {tools}

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
    r"larger|largest|small|smaller|junk|misc|leftover|leftovers|useless|unneeded|unnecessary)\b",
    re.I)
SPECIFIC = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|june?|july?|aug(ust)?|sep(t(ember)?)?|"
    r"oct(ober)?|nov(ember)?|dec(ember)?)\b|\d{2,}", re.I)


def _short(item):
    return str(item).rstrip("/").rsplit("/", 1)[-1]


def ambiguity(plan, request):
    """Return a question when a group phrase has several readings, else None. Deterministic.

    Two checks: the planner's own readings disagree, or a vague phrase ("the old runs") was
    resolved to several items although the request gives no date, number, name or "all".
    """
    for phrase, sets in plan.get("readings", {}).items():
        if len(sets) > 1:
            options = "; or ".join(", ".join(_short(i) for i in s) for s in sets[:4])
            return f'When you say "{phrase}", which do you mean: {options}? Nothing has been changed yet.'
    if not plan.get("effects"):
        return None
    for phrase, target in plan.get("aliases", {}).items():
        items = [t for t in re.split(r"[,;]\s*", str(target)) if t.strip()]
        if len(items) > 1 and VAGUE.search(str(phrase)) and VAGUE.search(request) \
                and not SPECIFIC.search(request):
            names = ", ".join(_short(i) for i in items[:8])
            return (f'"{phrase}" could mean several different sets of items. I found {names}. '
                    f"Which of these should I include? Nothing has been changed yet.")
    return None


def plan_prompt(history, aliases, state, tools, request):
    return PROMPT.format(
        history="\n".join(f"- {h}" for h in history) or "(none)",
        aliases=json.dumps(aliases), state=state, tools=", ".join(tools), request=request,
    )


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
