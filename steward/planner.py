"""Interpreter and planner: one LLM call per turn, outside the executor's history."""

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
 "effects": [ expected end-of-turn effects ]
}}

Set "clarify" only if a value that a tool strictly requires appears nowhere in the request,
the conversation, earlier tool results or the state, and could not be found by a read tool, so
that you would have to invent it. Do not ask when the request can be carried out as written.
A mistyped or approximate name that clearly matches one item in the state is not a reason to ask.

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

FALLBACK = {"clarify": None, "summary": [], "aliases": {}, "effects": []}


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
        "effects": [e for e in effects if isinstance(e, dict)] if isinstance(effects, list) else [],
    }


def plan_prompt(history, aliases, state, tools, request):
    return PROMPT.format(
        history="\n".join(f"- {h}" for h in history) or "(none)",
        aliases=json.dumps(aliases), state=state, tools=", ".join(tools), request=request,
    )
