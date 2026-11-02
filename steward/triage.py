"""Classify tool errors and return a targeted repair instruction."""

import json
import re

RULES = [
    ("auth", r"not authenticated|no user is currently logged|invalid access token|not logged",
     "Authenticate with the login tool using credentials from the conversation, then retry."),
    ("argument", r"path not allowed|unsupported path|invalid character|invalid (mode|priority|fields)",
     "Fix the argument to satisfy the tool's documented format, and do not retry it unchanged."),
    ("missing", r"no such|not found|does not exist|cannot (move|copy|remove|touch)",
     "Inspect the current state with a read tool, correct the name or location, then retry."),
    ("exists", r"file exists|already (exists|closed|resolved)",
     "The target is already in that state. Check whether this step is still needed."),
    ("precondition", r"must be|needs to be|not empty|not a directory|is a directory",
     "Perform the missing prerequisite action first, then retry."),
]


def is_error(result):
    text = str(result)
    if text.startswith("Error during execution"):
        return True
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and "error" in data


def classify(result):
    text = str(result).lower()
    for kind, pattern, repair in RULES:
        if re.search(pattern, text):
            return kind, repair
    return "unknown", "Read the error, inspect the state, and choose a different action."
