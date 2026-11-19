"""End-of-turn verifier: compares probed state with the planner's expected effects.

Purely deterministic. It sees state and effects, never the executor's reasoning.
"""


def _match(fs_state, path):
    tail = "/" + str(path).strip("/").removeprefix("./")
    return [p for p in fs_state if p == tail or p.endswith(tail)]


def check_effect(effect, snap):
    """Return True, False, or None when the effect cannot be checked on these backends."""
    kind = effect.get("type")
    fs = snap.get("GorillaFileSystem")
    tickets = snap.get("TicketAPI")
    messages = snap.get("MessageAPI")
    if kind in ("exists", "absent", "content_contains"):
        if fs is None:
            return None
        hits = _match(fs, effect.get("path", ""))
        if kind == "exists":
            return bool(hits)
        if kind == "absent":
            return not hits
        text = str(effect.get("text", "")).lower()
        return any(fs[p] is not None and text in fs[p].lower() for p in hits)
    if kind in ("ticket_status", "ticket_exists"):
        if tickets is None:
            return None
        queue = tickets.get("ticket_queue", [])
        if kind == "ticket_exists":
            return any(str(effect.get("title", "")).lower() == str(t.get("title", "")).lower()
                       for t in queue)
        return any(t.get("id") == effect.get("ticket_id")
                   and str(t.get("status", "")).lower() == str(effect.get("status", "")).lower()
                   for t in queue)
    if kind == "message_sent":
        if messages is None:
            return None
        text = str(effect.get("text", "")).lower()
        return any(text in str(m).lower() for m in messages.get("inbox", []))
    return None


def grounded(effects, known_text, fs_before):
    """Keep only effects anchored in what the user said or what exists.

    The planner can misspell names, use placeholders, or predict computed values. Checking
    such an effect would report a false failure, so it is dropped rather than verified.
    """
    known = known_text.lower()
    names = {p.rsplit("/", 1)[-1].lower() for p in fs_before}
    kept = []
    for effect in effects:
        kind = effect.get("type")
        if kind in ("exists", "absent"):
            base = str(effect.get("path", "")).rstrip("/").rsplit("/", 1)[-1].lower()
            if base and (base in known or base in names):
                kept.append(effect)
        elif kind in ("content_contains", "message_sent"):
            text = str(effect.get("text", "")).lower()
            if len(text.split()) >= 3 and text in known:
                kept.append(effect)
        else:
            kept.append(effect)
    return kept


def _covers(effect_path, changed):
    """True if a changed path is the effect's item, inside it, or a folder on the way to it."""
    parts = [p for p in str(effect_path).strip("/").removeprefix("./").split("/") if p]
    if not parts:
        return False
    tail = "/" + "/".join(parts)
    if changed.endswith(tail) or (tail + "/") in changed:
        return True
    return any(changed.endswith("/" + "/".join(parts[:k])) for k in range(1, len(parts)))


def unexpected(effects, before, after):
    """Changes the plan did not ask for, read from state. Empty when the plan cannot say.

    Only file paths and sent messages are compared. A plan with no file effects cannot judge
    file changes, and a plan with no message effects cannot judge messages, so those are skipped.
    """
    out = []
    fs_paths = [e.get("path", "") for e in effects if e.get("type") in ("exists", "absent", "content_contains")]
    fs_before = before.get("GorillaFileSystem")
    fs_after = after.get("GorillaFileSystem")
    if fs_paths and fs_before is not None and fs_after is not None:
        changed = sorted((fs_after.keys() ^ fs_before.keys())
                         | {p for p in fs_after.keys() & fs_before.keys() if fs_after[p] != fs_before[p]})
        # A move empties its source, so an item expected at a new place covers its old place.
        moved = {str(e.get("path", "")).rstrip("/").rsplit("/", 1)[-1]
                 for e in effects if e.get("type") == "exists"}
        for path in changed:
            gone = path in fs_before and path not in fs_after
            parts = path.strip("/").split("/")
            if gone and any(p in moved for p in parts):
                continue
            if not any(_covers(e, path) for e in fs_paths):
                out.append(path)
    expected_messages = sum(e.get("type") == "message_sent" for e in effects)
    msg_before = before.get("MessageAPI", {}).get("inbox")
    msg_after = after.get("MessageAPI", {}).get("inbox")
    if expected_messages and msg_before is not None and msg_after is not None:
        extra = len(msg_after) - len(msg_before) - expected_messages
        if extra > 0:
            out.append(f"{extra} message(s) sent that the request did not ask for")
    return out


def verify(effects, snap):
    """Split effects into (unmet, checked count). Uncheckable effects are not counted."""
    unmet, checked = [], 0
    for effect in effects:
        outcome = check_effect(effect, snap)
        if outcome is None:
            continue
        checked += 1
        if not outcome:
            unmet.append(effect)
    return unmet, checked
