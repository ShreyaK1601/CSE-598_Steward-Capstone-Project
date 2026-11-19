#!/usr/bin/env python3
"""Replay ground-truth calls through the preflight guard and list every call it would block.

A correct call that the guard blocks is a false positive, so this should print zero blocks.
No endpoint or key is needed.

    python scripts/guard_replay.py --datasets d1,d3
"""

import argparse
from collections import Counter

from steward import bfcl_env  # noqa: F401
from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call

from steward import specs
from steward.dataset import DATASETS


def replay(entry, truth, tag):
    config, classes = entry["initial_config"], entry["involved_classes"]
    _, instances = execute_multi_turn_func_call([], config, classes, tag, entry["id"])
    created, blocks, prev = set(), [], ""
    for turn, calls in enumerate(truth):
        message = entry["question"][turn] if turn < len(entry["question"]) else []
        text = " ".join(m["content"] for m in message if m["role"] == "user")
        for call in calls:
            name, args, owner = specs.parse_call(call, instances)
            if name:
                reason = specs.preflight(name, args, owner, instances, text, created, prev)
                if reason:
                    blocks.append((entry["id"], turn, call, reason))
                if name in specs.MUTATING and args is not None:
                    try:
                        _, new = specs.inverse(name, args, instances)
                        created.update(specs.made_by_call(name, args, instances, created, new))
                    except (KeyError, TypeError):
                        pass
            _, instances = execute_multi_turn_func_call([call], config, classes, tag, entry["id"])
        prev = text
    for key in [k for k in vars(multi_turn_utils) if k.startswith(tag)]:
        del vars(multi_turn_utils)[key]
    return blocks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", default="d1,d3")
    args = parser.parse_args()
    total = Counter()
    for dataset in args.datasets.split(","):
        entries, truth = DATASETS[dataset]()
        for entry in entries:
            for case_id, turn, call, reason in replay(entry, truth[entry["id"]], f"gr_{entry['id']}"):
                total[dataset] += 1
                print(f"{case_id} turn {turn}: {call}\n    {reason[:160]}")
        print(f"{dataset}: {total[dataset]} ground-truth calls blocked over {len(entries)} cases")


if __name__ == "__main__":
    main()
