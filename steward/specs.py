"""Declarative tool knowledge for the ops trio: preconditions, inverses, mutation class.

Held-out backends deliberately have no entries here, so they get only the generic
mechanisms (batch halt, triage, state brief, state-diff report).
"""

import ast
import difflib
import inspect
import re

from steward import probes

DELETE_WORDS = re.compile(
    r"\b(delet\w*|remov\w*|rm|eras\w*|discard\w*|clean\w*|purg\w*|get rid|trash\w*|"
    r"wip\w*|tidy\w*|dispos\w*|shred\w*|eliminat\w*|retract\w*|withdraw\w*|clear\w*)\b",
    re.I,
)

NEW_FILE_WORDS = re.compile(r"\b(new|creat\w*|draft\w*|start\w*|set up|make)\b", re.I)

MUTATING = {
    "touch", "mkdir", "echo", "mv", "cp", "rm", "rmdir",
    "create_ticket", "close_ticket", "resolve_ticket", "edit_ticket",
    "send_message", "delete_message", "add_contact",
}
IRREVERSIBLE = {"close_ticket", "resolve_ticket", "send_message"}


def parse_call(call, instances):
    """Turn "mv(source='a', destination='b')" into (name, args, class name)."""
    try:
        node = ast.parse(call.strip(), mode="eval").body
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        args = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
        owner = next((c for c, i in instances.items()
                      if callable(getattr(i, name, None)) and not name.startswith("_")), None)
        if node.args and owner:
            params = list(inspect.signature(getattr(instances[owner], name)).parameters)
            for param, value in zip(params, node.args):
                args[param] = ast.literal_eval(value)
        return name, args, owner
    except (SyntaxError, ValueError, AttributeError):
        return None, None, None


def _names(fs):
    return fs.ls(a=True)["current_directory_content"]


def _is_dir(fs, name):
    return name in _names(fs) and "Is a directory" in str(fs.cat(name).get("error", ""))


def _near(name, options):
    close = difflib.get_close_matches(str(name), options, n=1, cutoff=0.5)
    return f" Did you mean '{close[0]}'?" if close else ""


def _here(fs):
    return f"Current directory {fs.pwd()['current_working_directory']} contains {_names(fs)}."


def check_fs(name, a, fs):
    if name == "cd":
        folder = str(a.get("folder", "")).rstrip("/")
        if folder in (".", "..", ""):
            return None
        if "/" in folder:
            return f"cd moves one level at a time; '{folder}' is a path. {_here(fs)}"
        if not _is_dir(fs, folder):
            return f"no directory '{folder}' here.{_near(folder, _names(fs))} {_here(fs)}"
    elif name in ("touch", "mkdir"):
        new = a.get("file_name", a.get("dir_name", ""))
        if "/" in str(new):
            return f"{name} takes a bare name, not a path: '{new}'. Use cd first. {_here(fs)}"
        if new in _names(fs):
            return f"'{new}' already exists. {_here(fs)}"
    elif name == "echo":
        target = a.get("file_name")
        if target and target not in _names(fs):
            return (f"cannot write to '{target}': no such file here; create it with touch "
                    f"or cd to it first.{_near(target, _names(fs))} {_here(fs)}")
    elif name in ("mv", "cp"):
        src, dst = a.get("source", ""), a.get("destination", "")
        if src not in _names(fs):
            return f"source '{src}' is not here.{_near(src, _names(fs))} {_here(fs)}"
        if "/" in str(dst):
            return (f"{name} destination must be a bare name, not a path: '{dst}'. "
                    f"Name a directory in the current directory. {_here(fs)}")
        if dst in _names(fs) and not _is_dir(fs, dst):
            return f"'{dst}' already exists and is not a directory. {_here(fs)}"
    elif name in ("rm", "rmdir"):
        target = a.get("file_name", a.get("dir_name", ""))
        if target not in _names(fs):
            return f"'{target}' is not here.{_near(target, _names(fs))} {_here(fs)}"
    return None


def check_ticket(name, a, tickets):
    if name == "create_ticket":
        if not tickets.current_user:
            return "not logged in to the ticket system; call ticket_login with credentials first."
        if not 1 <= int(a.get("priority", 1)) <= 5:
            return "priority must be between 1 and 5."
    elif name in ("close_ticket", "resolve_ticket", "edit_ticket"):
        ticket = tickets.get_ticket(a.get("ticket_id"))
        if "error" in ticket:
            known = [t.get("id") for t in tickets.ticket_queue]
            return f"ticket {a.get('ticket_id')} does not exist; known ids: {known}."
        if name == "close_ticket" and ticket.get("status") == "Closed":
            return f"ticket {a.get('ticket_id')} is already closed."
    return None


def check_message(name, a, messages):
    if name in ("send_message", "delete_message"):
        if not messages.current_user:
            return "no user logged in; call message_login first."
    if name == "send_message" and a.get("receiver_id") not in messages.user_map.values():
        return (f"receiver id '{a.get('receiver_id')}' is unknown; use get_user_id. "
                f"Known users: {messages.user_map}.")
    return None


CHECKS = {
    "GorillaFileSystem": check_fs,
    "TicketAPI": check_ticket,
    "MessageAPI": check_message,
}


def named(item, text):
    """True if the request names this item, by full name or by its name without extension."""
    item = str(item).strip("/").rsplit("/", 1)[-1]
    stem = item.split(".", 1)[0]
    for word in {item, stem}:
        if len(word) >= 3 and re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", text, re.I):
            return True
    return False


def deletion_requested(target, folders, turn_text, prev_text):
    """A pre-existing item may be deleted only if the user asked to delete that item.

    The delete word and the item's name, or the name of a folder holding it ("delete the files in
    Drafts"), must both come from the user: in the current request, or, when the current request
    is only an answer (no delete word of its own), across it and the request before it.
    "Remove it" alone names nothing, so it does not permit deletion.
    """
    if DELETE_WORDS.search(turn_text):
        text = turn_text
    elif DELETE_WORDS.search(prev_text):
        text = turn_text + " " + prev_text
    else:
        return False
    return any(named(item, text) for item in [target, *folders])


CONFIRM_WORDS = re.compile(r"\b(yes|yeah|confirm\w*|go ahead|proceed)\b", re.I)
BULK_LIMIT = 2


def bulk_reason(target, fs, text, turn_text, created):
    """Deleting a folder's contents in bulk ("delete everything in scratch") needs a confirmation.

    Applies only when the item itself was not named, so the permission comes from naming its
    folder, and the folder holds more than BULK_LIMIT existing items.
    """
    if fs is None or named(target, text) or CONFIRM_WORDS.search(turn_text):
        return None
    existing = [n for n in _names(fs) if n not in created and not n.startswith(".")]
    if len(existing) <= BULK_LIMIT:
        return None
    return (f"refused: this would delete {len(existing)} existing items in "
            f"{fs.pwd()['current_working_directory']} that the user did not name one by one: "
            f"{existing}. List them and ask the user to confirm before deleting anything.")


def overwrite_reason(args, instances, turn_text, prev_text, created):
    """Refuse to replace the content of a user's existing file unless the user asked for it."""
    fs = instances.get("GorillaFileSystem")
    target = args.get("file_name")
    if fs is None or not target or target in created or target not in _names(fs):
        return None
    if not str(fs.cat(target).get("file_content", "")).strip():
        return None
    if NEW_FILE_WORDS.search(turn_text):
        return (f"refused: '{target}' already exists with content, and the request asks for a new "
                f"file. Writing would replace the existing content. Ask the user how to proceed.")
    if not named(target, turn_text + " " + prev_text):
        return (f"refused: writing would replace the existing content of '{target}', which the "
                f"user did not name. Ask the user which file to write to.")
    return None


def preflight(name, args, owner, instances, turn_text, created, prev_text=""):
    """Return why this call must not run, or None. Uses read-only calls only."""
    if owner not in CHECKS:
        return None
    # Deleting data the user did not ask to delete is the stakeholder's critical failure.
    if name == "delete_message":
        if not DELETE_WORDS.search(turn_text):
            return "refused: deleting a message was not requested by the user."
    elif name in ("rm", "rmdir"):
        target = args.get("file_name", args.get("dir_name"))
        fs = instances.get("GorillaFileSystem")
        folders = fs.pwd()["current_working_directory"].strip("/").split("/")[1:] if fs else []
        if target not in created:
            if not deletion_requested(target, folders, turn_text, prev_text):
                return (f"refused: {name} of '{target}', which Steward did not create and the user "
                        f"did not name for deletion. Ask the user which item to delete.")
            text = turn_text + " " + prev_text
            reason = bulk_reason(target, fs, text, turn_text, created)
            if reason:
                return reason
            places = [p for p in probes.walk_fs(fs) if p.rsplit("/", 1)[-1] == target] if fs else []
            if len(places) > 1 and not any(named(f, text) for f in folders):
                return (f"refused: '{target}' exists in {len(places)} places ({', '.join(places)}) "
                        f"and the user did not say which folder. Ask the user which one to delete.")
    elif name == "echo":
        reason = overwrite_reason(args, instances, turn_text, prev_text, created)
        if reason:
            return reason
    try:
        return CHECKS[owner](name, args, instances[owner])
    except (TypeError, ValueError, KeyError):
        return None


def made_by_call(name, args, instances, created, new_name):
    """Names this call makes Steward's own if it succeeds. Call before executing it.

    Items Steward created, or renamed from items it created, are not the user's existing data,
    so later edits to them are not refused.
    """
    names = [new_name] if new_name else []
    if name == "mv" and args.get("source") in created:
        fs = instances.get("GorillaFileSystem")
        if fs is not None and not _is_dir(fs, args.get("destination", "")):
            names.append(args["destination"])
    return names


def inverse(name, args, instances):
    """Compute (undo calls, created name) before a mutating call runs.

    Returns (None, None) when the tool API offers no way back.
    """
    q = repr
    fs = instances.get("GorillaFileSystem")
    if name == "touch":
        return [f"rm(file_name={q(args['file_name'])})"], args["file_name"]
    if name == "mkdir":
        return [f"rmdir(dir_name={q(args['dir_name'])})"], args["dir_name"]
    if name == "echo" and args.get("file_name"):
        old = fs.cat(args["file_name"]).get("file_content", "")
        return [f"echo(content={q(old)}, file_name={q(args['file_name'])})"], None
    if name == "mv":
        src, dst = args["source"], args["destination"]
        if _is_dir(fs, dst):
            # The tools cannot name a parent as a destination, so this has no inverse.
            return None, None
        return [f"mv(source={q(dst)}, destination={q(src)})"], None
    if name == "cp":
        src, dst = args["source"], args["destination"]
        if _is_dir(fs, dst):
            return [f"cd(folder={q(dst)})", f"rm(file_name={q(src)})", "cd(folder='..')"], None
        return [f"rm(file_name={q(dst)})"], dst
    if name == "send_message":
        return [f"delete_message(receiver_id={q(args['receiver_id'])})"], None
    if name in ("close_ticket", "resolve_ticket"):
        ticket = instances["TicketAPI"].get_ticket(args["ticket_id"])
        return [f"edit_ticket(ticket_id={args['ticket_id']}, "
                f"updates={{'status': {q(ticket.get('status'))}}})"], None
    return None, None
