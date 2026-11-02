#!/usr/bin/env python3
"""Steward command line. Dry-run by default: shows the plan and changes nothing without approval.

    python -m steward.cli "Move the March runs into scratch/archive"
    python -m steward.cli --approve "Move ..." "Now tell priya: done."

Runs against the lab_ops sandbox (simulated backends), never against real systems.
"""

import argparse
import json
import sys
from copy import deepcopy

from steward import agent
from steward.dataset import LAB_CONFIG, populate_test_cases_with_predefined_functions

CLASSES = ["GorillaFileSystem", "TicketAPI", "MessageAPI"]


def printer(kind, data):
    if kind == "plan":
        plan = data["plan"]
        print("\nPLAN")
        for line in plan["summary"]:
            print(f"  {line}")
        if plan["effects"]:
            print("  expected effects:")
            for effect in plan["effects"]:
                print(f"    {json.dumps(effect)}")
        if plan["aliases"]:
            print(f"  resolved: {json.dumps(plan['aliases'])}")
    elif kind == "tool":
        print(f"  TOOL   {data['call']}\n         -> {str(data['result'])[:140]}")
    elif kind == "blocked":
        print(f"  BLOCK  {data['call']}\n         -> {data['reason'][:200]}")
    elif kind == "verify":
        print(f"  VERIFY unmet: {json.dumps(data['unmet'])}; one repair attempt")
    elif kind == "rollback":
        print(f"  UNDO   {data['calls']}" + (f"\n         could not undo: {data['stuck']}" if data["stuck"] else ""))
    elif kind == "report":
        report = data["report"]
        print(f"\nREPORT [{report['verdict']}]\n  {report['text'] or '; '.join(report['changes']) or 'no changes'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requests", nargs="+", help="one request per conversation turn")
    parser.add_argument("--approve", action="store_true", help="execute after showing each plan")
    parser.add_argument("--session", default="cli", help="name for this sandbox session")
    args = parser.parse_args()

    def approve(_plan):
        if not args.approve:
            print("\nDRY RUN: nothing executed. Re-run with --approve to execute.")
        return args.approve

    entry = {
        "id": f"multi_turn_cli_{args.session}",
        "question": [[{"role": "user", "content": text}] for text in args.requests],
        "initial_config": deepcopy(LAB_CONFIG),
        "involved_classes": CLASSES,
        "path": [],
    }
    populate_test_cases_with_predefined_functions([entry])
    config = agent.Config(**agent.STEWARD, approve=approve, on_event=printer)
    handler = agent.StewardHandler(f"cli_{args.session}", config)
    print("=" * 72)
    for number, text in enumerate(args.requests):
        print(f"REQUEST {number + 1}: {text}")
    handler.inference_multi_turn_prompting(entry, False, True)


if __name__ == "__main__":
    sys.exit(main())
