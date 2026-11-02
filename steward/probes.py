"""Read-only views of backend state. Nothing here changes a backend."""

import copy
import json


def walk_fs(fs):
    """Flatten a GorillaFileSystem tree into {path: None for dirs, content for files}."""
    out = {}

    def visit(node, path):
        for name, item in node.contents.items():
            child = f"{path}/{name}"
            if hasattr(item, "contents"):
                out[child] = None
                visit(item, child)
            else:
                out[child] = item.content

    visit(fs.root, "/" + fs.root.name)
    return out


def snapshot(instances):
    """Capture the observable state of every backend as plain data."""
    snap = {}
    for class_name, inst in instances.items():
        if class_name == "MathAPI":
            continue
        if class_name == "GorillaFileSystem":
            snap[class_name] = walk_fs(inst)
        else:
            snap[class_name] = {
                k: copy.deepcopy(v) for k, v in vars(inst).items()
                if not k.startswith("_") and _plain(v)
            }
    return snap


def _plain(value):
    try:
        json.dumps(value)
        return True
    except TypeError:
        return False


def diff(before, after):
    """Describe what changed between two snapshots, from state and not from the model."""
    changes = []
    for class_name, now in after.items():
        was = before.get(class_name, {})
        if class_name == "GorillaFileSystem":
            for path in sorted(now.keys() - was.keys()):
                changes.append(f"created {path}")
            for path in sorted(was.keys() - now.keys()):
                changes.append(f"removed {path}")
            for path in sorted(now.keys() & was.keys()):
                if now[path] != was[path]:
                    changes.append(f"modified {path}")
        else:
            for key in sorted(now.keys() | was.keys()):
                if now.get(key) != was.get(key):
                    changes.append(f"{class_name}.{key} changed")
    return changes


def cwd(instances):
    fs = instances.get("GorillaFileSystem")
    return fs.pwd()["current_working_directory"] if fs else None


def brief(instances, limit=1800):
    """Short state summary given to the planner and executor at the start of a turn."""
    lines = []
    for class_name, data in snapshot(instances).items():
        if class_name == "GorillaFileSystem":
            lines.append(f"current directory: {cwd(instances)}")
            lines.append("file tree: " + ", ".join(
                p + ("/" if v is None else "") for p, v in sorted(data.items())))
        elif class_name == "TicketAPI":
            tickets = [
                {k: t.get(k) for k in ("id", "title", "status", "priority")}
                for t in data.get("ticket_queue", [])
            ]
            lines.append(f"tickets: {json.dumps(tickets)}; "
                         f"ticket user: {data.get('current_user')}")
        elif class_name == "MessageAPI":
            lines.append(f"message users: {json.dumps(data.get('user_map', {}))}; "
                         f"message user: {data.get('current_user')}")
        else:
            lines.append(f"{class_name}: {json.dumps(data)}")
    text = "\n".join(lines)
    return text if len(text) <= limit else text[:limit] + " ...(truncated)"
