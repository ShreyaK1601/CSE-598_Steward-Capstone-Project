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

from steward import agent, planner
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
        for phrase, names in plan.get("items", {}).items():
            print(f"  {phrase}: {len(names)} items")
            for name in names:
                print(f"    - {name}")
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


def confirm_undo(unmet, journal):
    """Stop on a failed check: show what is wrong and undo only if the person approves."""
    print(f"\nCHECK FAILED. Unmet: {json.dumps(unmet)}")
    print("Changes this turn:")
    for entry in journal:
        print(f"  {entry['call']}" + ("" if entry["undo"] else "  (cannot be undone)"))
    return ask("Undo these changes? [y/N] ")


class Irreversible:
    """Warn before changes the tools cannot undo, separately from approving the plan.

    The plan's moves are listed and confirmed once per turn when the plan is approved. A call
    with no inverse that the plan did not list is confirmed on its own before it runs.
    """

    def __init__(self):
        self.accepted = False

    def plan(self, plan):
        self.accepted = False
        moves = planner.irreversible(plan)
        if not moves:
            return True
        print("\nWARNING: these moves cannot be undone with the available tools:")
        for move in moves:
            print(f"  {move}")
        self.accepted = ask("Make these moves anyway? [y/N] ")
        return self.accepted

    def call(self, call):
        if self.accepted:
            return True
        print(f"\nWARNING: {call} cannot be undone with the available tools.")
        self.accepted = ask("Run it anyway? [y/N] ")
        return self.accepted


def ask(prompt):
    try:
        return input(prompt).strip().lower() == "y"
    except EOFError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requests", nargs="+", help="one request per conversation turn")
    parser.add_argument("--approve", action="store_true", help="execute after showing each plan")
    parser.add_argument("--session", default="cli", help="name for this sandbox session")
    args = parser.parse_args()

    guard = Irreversible()

    def approve(plan):
        if not args.approve:
            moves = planner.irreversible(plan)
            if moves:
                print("\nWARNING: these moves cannot be undone with the available tools:")
                for move in moves:
                    print(f"  {move}")
            print("\nDRY RUN: nothing executed. Re-run with --approve to execute.")
            return False
        return guard.plan(plan)

    entry = {
        "id": f"multi_turn_cli_{args.session}",
        "question": [[{"role": "user", "content": text}] for text in args.requests],
        "initial_config": deepcopy(LAB_CONFIG),
        "involved_classes": CLASSES,
        "path": [],
    }
    populate_test_cases_with_predefined_functions([entry])
    settings = dict(agent.STEWARD, rollback=False)
    config = agent.Config(**settings, approve=approve, confirm_undo=confirm_undo,
                          confirm_irreversible=guard.call, on_event=printer)
    handler = agent.StewardHandler(f"cli_{args.session}", config)
    print("=" * 72)
    for number, text in enumerate(args.requests):
        print(f"REQUEST {number + 1}: {text}")
    handler.inference_multi_turn_prompting(entry, False, True)


if __name__ == "__main__":
    sys.exit(main())
