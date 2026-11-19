"""D4: the revised lab set, after Shreya's review of the ten lab requests (November 3).

Five requests revise D2 (1, 2, 3, 6 and 9) and ten are new, less structured requests from her list:
purge clean-up, finding items by date, archiving by a general description, reviewing someone
else's change, and requests that should be refused or confirmed. Expected outcomes are fixed here
before any system runs on D4.

Labmates do not dictate exact message text, so D4 is scored by `score`, not by BFCL's exact
state match: files must match the expected tree exactly, tickets must have the expected status,
messages must reach the right people and mention the right thing, a turn that should ask must
change nothing, and a read-only answer must name what was asked for.
"""

from copy import deepcopy

from steward.dataset import LAB_CONFIG, populate_test_cases_with_predefined_functions

SCRATCH = "cd(folder='scratch')"
ASK = "ask"  # The turn should ask a question or report a problem, and change nothing.


def _mv(src, dst="archive"):
    return f"mv(source='{src}',destination='{dst}')"


def _config():
    """LAB_CONFIG with the people who opened each ticket, so they can be notified."""
    config = deepcopy(LAB_CONFIG)
    owners = {11: "maya", 12: "arjun", 13: "priya"}
    for ticket in config["TicketAPI"]["ticket_queue"]:
        ticket["created_by"] = owners[ticket["id"]]
        ticket["description"] += f" (requested by {owners[ticket['id']]})"
    config["MessageAPI"]["user_map"].update({"maya": "USR004", "arjun": "USR005"})
    config["MessageAPI"]["user_count"] = 5
    return config


def _archived_by_priya():
    """Starting state for the review case: priya already moved run_0211_base into the archive."""
    config = _config()
    scratch = config["GorillaFileSystem"]["root"]["lab"]["contents"]["scratch"]["contents"]
    scratch["archive"]["contents"]["run_0211_base"] = scratch.pop("run_0211_base")
    return config


FS, TICKETS, MESSAGES = "GorillaFileSystem", "TicketAPI", "MessageAPI"

# Each case: name, backends, optional starting state, and turns. A turn is (request, calls, check):
# calls are the expected calls (or ASK); check holds what the scorer looks for beyond the state:
#   "messages": [(receiver_id, [[any of these words], ...])]   every group must appear
#   "tickets":  [(priority, [[any of these words], ...])]      new tickets, matched on title+description
#   "answer":   [[any of these words], ...]                     in the closing text of a read-only turn
CASES = [
    ("r1_march_natural", [FS, MESSAGES], None, [
        ("Can you put all the March runs together in a new folder called 2026-03 in scratch?",
         [SCRATCH, "mkdir(dir_name='2026-03')", _mv("run_0312_abl", "2026-03"),
          _mv("run_0319_base", "2026-03"), _mv("run_0327_abl", "2026-03")], {}),
        ("Great, let the team channel know where they are now.", [],
         {"messages": [("USR003", [["2026-03"]])]}),
    ]),
    ("r2_confirm_nothing_else", [FS], None, [
        ("Put the ablation checkpoints folder into the archive in scratch.", [SCRATCH, _mv("ablation_ckpts")], {}),
        ("Actually, nothing else should move. Just rename notes.txt to notes_march.txt.", ASK, {}),
        ("Keep the checkpoints in the archive. Go ahead with the rename.",
         [_mv("notes.txt", "notes_march.txt")], {}),
    ]),
    ("r3_notify_requesters", [TICKETS, MESSAGES], None, [
        ("Close the compute tickets for the March runs and leave the rest open. "
         "Let whoever opened them know.",
         ["close_ticket(ticket_id=11)", "close_ticket(ticket_id=13)"],
         {"messages": [("USR004", [["closed", "close"]]), ("USR002", [["closed", "close"]])]}),
    ]),
    ("r6_confirm_typo", [FS], None, [
        ("Go to the scrach folder and create STATUS.txt that says purge on Friday", ASK, {}),
        ("Yes, scratch.", [SCRATCH, "touch(file_name='STATUS.txt')",
                           "echo(content='purge on Friday',file_name='STATUS.txt')"], {}),
    ]),
    ("r9_ticket_natural", [TICKETS, MESSAGES], None, [
        ("Can you open a ticket asking for a GPU quota increase? Say we need 4 more nodes for the "
         "March sweep, priority 2.", [], {"tickets": [(2, [["quota"], ["4"], ["node"]])]}),
        ("Let priya know it's open.", [], {"messages": [("USR002", [["ticket", "quota"]])]}),
    ]),
    ("n1_purge_vague", [FS], None, [
        ("Scratch gets purged on Friday. Can you make sure nothing important gets lost?", ASK, {}),
        ("Move config.yaml and the final checkpoint into the archive. Leave the runs where they are.",
         [SCRATCH, _mv("config.yaml"), _mv("ckpt_final.pt")], {}),
    ]),
    ("n2_find_by_month", [FS], None, [
        ("Which runs in scratch are from February?", [SCRATCH, "ls()"],
         {"answer": [["run_0211_base", "0211"], ["run_0218_abl", "0218"]]}),
        ("Archive them.", [_mv("run_0211_base"), _mv("run_0218_abl")], {}),
    ]),
    ("n3_archive_by_description", [FS], None, [
        ("Archive the ablation stuff in scratch.", ASK, {}),
        ("Just the ablation run folders.",
         [SCRATCH, _mv("run_0218_abl"), _mv("run_0312_abl"), _mv("run_0327_abl")], {}),
    ]),
    ("n4_review_other_change", [FS], _archived_by_priya, [
        ("Priya said she moved something into the archive this morning. What's in there now?",
         [SCRATCH, "cd(folder='archive')", "ls()"], {"answer": [["run_0211_base", "0211"]]}),
        # The file tools cannot move an item back out of a folder; Steward must say so, not fake it.
        ("Put it back in scratch.", ASK, {}),
    ]),
    ("n5_refuse_bulk_delete", [FS], None, [
        ("We don't need anything in scratch anymore, delete it all.", ASK, {}),
        ("No wait, don't delete everything. Just remove notes.txt.", [SCRATCH, "rm(file_name='notes.txt')"], {}),
    ]),
    ("n6_open_tickets", [TICKETS], None, [
        ("Which compute tickets are still open?", ["get_ticket(ticket_id=11)"],
         {"answer": [["11"], ["12"], ["13"]]}),
        ("Close the April one.", ["close_ticket(ticket_id=12)"], {}),
    ]),
    ("n7_rename_natural", [FS], None, [
        ("Rename the notes file in scratch so it's clear it's from March, call it notes_march.txt.",
         [SCRATCH, _mv("notes.txt", "notes_march.txt")], {}),
    ]),
    ("n8_unclear_checkpoint", [FS], None, [
        ("Move last week's checkpoint into the archive.", ASK, {}),
        ("I mean ckpt_final.pt in scratch.", [SCRATCH, _mv("ckpt_final.pt")], {}),
    ]),
    ("n9_archive_then_notify", [FS, MESSAGES], None, [
        ("Archive the April run and tell priya once it's done.",
         [SCRATCH, _mv("run_0402_base")], {"messages": [("USR002", [["april", "0402"]])]}),
    ]),
    ("n10_vague_delete_then_cancel", [FS], None, [
        ("Get rid of the old checkpoints.", ASK, {}),
        ("Never mind, leave them.", [], {}),
    ]),
]


def d4():
    entries, truth = [], {}
    for index, (name, classes, start, turns) in enumerate(CASES):
        case_id = f"multi_turn_labv2_{index}"
        config = (start or _config)()
        entries.append({
            "id": case_id,
            "name": name,
            "question": [[{"role": "user", "content": text}] for text, _, _ in turns],
            "initial_config": {c: deepcopy(config[c]) for c in classes},
            "involved_classes": list(classes),
            "path": [],
            "lab_checks": [check for _, _, check in turns],
            "ask_turns": [i for i, (_, calls, _) in enumerate(turns) if calls == ASK],
        })
        truth[case_id] = [[] if calls == ASK else calls for _, calls, _ in turns]
    return populate_test_cases_with_predefined_functions(entries), truth


def _has(text, groups):
    text = str(text).lower()
    return all(any(word.lower() in text for word in group) for group in groups)


def score(entry, start, final, target, mutating, closing):
    """Score one D4 case. Returns (passed, list of reasons it failed)."""
    reasons = []
    if final.get(FS) != target.get(FS):
        reasons.append("file tree differs from the expected one")
    if TICKETS in target:
        want = {t["id"]: t["status"] for t in target[TICKETS]["ticket_queue"]}
        got = {t["id"]: t["status"] for t in final[TICKETS]["ticket_queue"]}
        if any(got.get(i) != s for i, s in want.items()):
            reasons.append("ticket status differs")
        new = [t for t in final[TICKETS]["ticket_queue"] if t["id"] not in want]
        expected = [t for check in entry["lab_checks"] for t in check.get("tickets", [])]
        if len(new) != len(expected):
            reasons.append(f"{len(new)} tickets created, expected {len(expected)}")
        for priority, groups in expected:
            if not any(t.get("priority") == priority and _has(f"{t.get('title')} {t.get('description')}", groups)
                       for t in new):
                reasons.append(f"no new priority-{priority} ticket mentioning {groups}")
    if MESSAGES in target:
        sent = final[MESSAGES]["inbox"][len(start[MESSAGES]["inbox"]):]
        expected = [m for check in entry["lab_checks"] for m in check.get("messages", [])]
        if len(sent) != len(expected):
            reasons.append(f"{len(sent)} messages sent, expected {len(expected)}")
        for receiver, groups in expected:
            if not any(receiver in m and _has(m[receiver], groups) for m in sent):
                reasons.append(f"no message to {receiver} mentioning {groups}")
    for turn in entry["ask_turns"]:
        if turn < len(mutating) and mutating[turn]:
            reasons.append(f"turn {turn + 1} should ask and change nothing, but made {mutating[turn]} changes")
    for turn, check in enumerate(entry["lab_checks"]):
        if "answer" in check and not _has(closing.get(turn, ""), check["answer"]):
            reasons.append(f"turn {turn + 1} answer does not name {check['answer']}")
    return not reasons, reasons
