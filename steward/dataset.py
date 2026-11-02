"""Evaluation sets. All are fixed here so every system sees the same cases."""

import random
from copy import deepcopy

from steward import bfcl_env  # noqa: F401
from bfcl_eval.utils import (
    load_dataset_entry,
    load_ground_truth_entry,
    populate_test_cases_with_predefined_functions,
)

OPS = {"GorillaFileSystem", "TicketAPI", "MessageAPI"}
SAMPLE_SEED = 598
HELD_OUT_SAMPLE = 30


def _used(entry):
    return set(entry["involved_classes"]) - {"MathAPI"}


def _load(category, keep):
    entries = load_dataset_entry(category, include_language_specific_hint=False)
    truth = {g["id"]: g["ground_truth"] for g in load_ground_truth_entry(category)}
    picked = [e for e in entries if keep(e)]
    return picked, {e["id"]: truth[e["id"]] for e in picked}


def _ops(entry):
    return bool(_used(entry)) and _used(entry) <= OPS


def d1():
    return _load("multi_turn_base", _ops)


def d1h():
    entries, truth = _load("multi_turn_base", lambda e: _used(e) and not (_used(e) & OPS))
    chosen = sorted(random.Random(SAMPLE_SEED).sample(range(len(entries)), HELD_OUT_SAMPLE))
    entries = [entries[i] for i in chosen]
    return entries, {e["id"]: truth[e["id"]] for e in entries}


def d3():
    return _load("multi_turn_miss_param", _ops)


# D2: lab operations set. Written by the team acting as proxy for the stakeholder, with each
# expected outcome fixed before any system ran. Directory names are invented placeholders.
LAB_TREE = {"lab": {"type": "directory", "contents": {
    "scratch": {"type": "directory", "contents": {
        "run_0211_base": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "feb base"}}},
        "run_0218_abl": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "feb abl"}}},
        "run_0312_abl": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "mar abl 1"}}},
        "run_0319_base": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "mar base"}}},
        "run_0327_abl": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "mar abl 2"}}},
        "run_0402_base": {"type": "directory", "contents": {"log.txt": {"type": "file", "content": "apr base"}}},
        "ablation_ckpts": {"type": "directory", "contents": {
            "ckpt_a.pt": {"type": "file", "content": "placeholder a"},
            "ckpt_b.pt": {"type": "file", "content": "placeholder b"}}},
        "ckpt_final.pt": {"type": "file", "content": "placeholder final"},
        "config.yaml": {"type": "file", "content": "lr: 0.001"},
        "notes.txt": {"type": "file", "content": "purge on friday\nkeep raw data\nask before moving\n"},
        "archive": {"type": "directory", "contents": {}},
    }},
    "shared": {"type": "directory", "contents": {
        "README.txt": {"type": "file", "content": "lab shared space"}}},
}}}

LAB_CONFIG = {
    "GorillaFileSystem": {"root": LAB_TREE},
    "TicketAPI": {
        "ticket_queue": [
            {"id": 11, "title": "Compute request: March ablation sweep", "description": "32 GPUs for run_0312_abl", "status": "Open", "priority": 2, "created_by": "steward_lab"},
            {"id": 12, "title": "Compute request: April baseline", "description": "8 GPUs for run_0402_base", "status": "Open", "priority": 3, "created_by": "steward_lab"},
            {"id": 13, "title": "Compute request: March baseline", "description": "16 GPUs for run_0319_base", "status": "Open", "priority": 3, "created_by": "steward_lab"},
        ],
        "ticket_counter": 14,
        "current_user": "steward_lab",
    },
    "MessageAPI": {
        "user_count": 3,
        "user_map": {"lab_ops": "USR001", "priya": "USR002", "team_channel": "USR003"},
        "inbox": [],
        "message_count": 0,
        "current_user": "USR001",
    },
}

SCRATCH = "cd(folder='scratch')"


def _mv(src, dst="archive"):
    return f"mv(source='{src}',destination='{dst}')"


LAB_CASES = [
    (["GorillaFileSystem", "MessageAPI"], [
        ("Consolidate the March runs into a new folder called 2026-03 inside scratch.",
         [SCRATCH, "mkdir(dir_name='2026-03')", _mv("run_0312_abl", "2026-03"),
          _mv("run_0319_base", "2026-03"), _mv("run_0327_abl", "2026-03")]),
        ("Tell the team channel exactly this: March runs are now in scratch/2026-03.",
         ["send_message(receiver_id='USR003',message='March runs are now in scratch/2026-03.')"]),
    ]),
    (["GorillaFileSystem"], [
        ("Put the ablation checkpoints folder into the archive in scratch.",
         [SCRATCH, _mv("ablation_ckpts")]),
        ("Actually, nothing else should move. Just rename notes.txt to notes_march.txt.",
         [_mv("notes.txt", "notes_march.txt")]),
    ]),
    (["TicketAPI", "MessageAPI"], [
        ("Close the compute request tickets for the March runs. Leave any others open.",
         ["close_ticket(ticket_id=11)", "close_ticket(ticket_id=13)"]),
        ("Send priya exactly this: March compute tickets are closed.",
         ["send_message(receiver_id='USR002',message='March compute tickets are closed.')"]),
    ]),
    (["GorillaFileSystem"], [
        ("Move the old runs into the archive.", []),
        ("I mean the February ones in scratch.",
         [SCRATCH, _mv("run_0211_base"), _mv("run_0218_abl")]),
    ]),
    (["GorillaFileSystem"], [
        ("Scratch is getting crowded. Move ckpt_final.pt and config.yaml into its archive, and do not delete anything.",
         [SCRATCH, _mv("ckpt_final.pt"), _mv("config.yaml")]),
    ]),
    (["GorillaFileSystem"], [
        ("Go to the scrach folder and create STATUS.txt containing exactly: purge on Friday",
         [SCRATCH, "touch(file_name='STATUS.txt')", "echo(content='purge on Friday',file_name='STATUS.txt')"]),
    ]),
    (["GorillaFileSystem"], [
        ("Back up config.yaml from scratch into the archive and keep the original where it is.",
         [SCRATCH, "cp(source='config.yaml',destination='archive')"]),
        ("Inside the archive, rename that backup to config_bak.yaml.",
         ["cd(folder='archive')", _mv("config.yaml", "config_bak.yaml")]),
    ]),
    (["GorillaFileSystem"], [
        ("Move run_0501_base from scratch into the archive.", []),
        ("Sorry, that one does not exist. Move run_0402_base into the archive instead.",
         [SCRATCH, _mv("run_0402_base")]),
    ]),
    (["TicketAPI", "MessageAPI"], [
        ("Open a ticket titled 'GPU quota increase' with description 'Need 4 more nodes for the March sweep' at priority 2.",
         ["create_ticket(title='GPU quota increase',description='Need 4 more nodes for the March sweep',priority=2)"]),
        ("Let priya know with exactly this message: Quota ticket opened.",
         ["send_message(receiver_id='USR002',message='Quota ticket opened.')"]),
    ]),
    (["GorillaFileSystem"], [
        ("How many lines are in notes.txt in scratch?",
         [SCRATCH, "wc(file_name='notes.txt',mode='l')"]),
        ("Record that in a new file summary.txt in the same folder, with the content in the form lines: N",
         ["touch(file_name='summary.txt')", "echo(content='lines: 3',file_name='summary.txt')"]),
    ]),
]


def d2():
    entries, truth = [], {}
    for i, (classes, turns) in enumerate(LAB_CASES):
        case_id = f"multi_turn_labops_{i}"
        config = {c: deepcopy(LAB_CONFIG[c]) for c in classes}
        entries.append({
            "id": case_id,
            "question": [[{"role": "user", "content": text}] for text, _ in turns],
            "initial_config": config,
            "involved_classes": list(classes),
            "path": [],
        })
        truth[case_id] = [calls for _, calls in turns]
    return populate_test_cases_with_predefined_functions(entries), truth


DATASETS = {"d1": d1, "d1h": d1h, "d2": d2, "d3": d3}
