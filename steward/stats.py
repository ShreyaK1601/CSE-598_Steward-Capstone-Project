"""Summary tables: Wilson intervals, exact McNemar tests, per-system metrics."""

import csv
import math
from collections import defaultdict
from math import comb


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def mcnemar(a, b):
    """Exact two-sided McNemar test on paired pass/fail lists."""
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    tail = sum(comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n
    return only_a, only_b, min(1.0, 2 * tail)


def _load(scored):
    data = defaultdict(lambda: defaultdict(dict))
    for path in sorted(scored.glob("*/*.csv")):
        system, repeat = path.stem.rsplit("_r", 1)
        with open(path) as f:
            data[path.parent.name][system][int(repeat)] = list(csv.DictReader(f))
    return data


def _sum(rows, key):
    return sum(float(r[key]) for r in rows)


def write_summary(scored, target):
    lines = ["# Measured results", ""]
    for dataset, systems in sorted(_load(scored).items()):
        lines += [f"## {dataset}", "",
                  "| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | "
                  "Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | "
                  "Tokens/case | Wall s/case |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for system, repeats in sorted(systems.items()):
            rows = [r for rep in repeats.values() for r in rep]
            n = len(rows)
            k = int(_sum(rows, "passed"))
            low, high = wilson(k, n)
            calls = _sum(rows, "tool_calls")
            errors = _sum(rows, "tool_errors")
            with_error = [r for r in rows if float(r["tool_errors"]) > 0]
            recovered = sum(int(r["passed"]) for r in with_error)
            per = ", ".join(f"{int(_sum(rep, 'passed'))}/{len(rep)}" for _, rep in sorted(repeats.items()))
            tokens = (_sum(rows, "input_tokens") + _sum(rows, "output_tokens")) / n
            mismatch = sum(r["error_type"].endswith("instance_state_mismatch") for r in rows)
            lines.append(
                f"| {system} | {len(repeats)} | {per} | {100 * k / n:.1f} ({100 * low:.1f}-{100 * high:.1f}) "
                f"| {calls / n:.1f} | {100 * errors / max(calls, 1):.1f}% | {int(_sum(rows, 'blocked'))} "
                f"| {recovered}/{len(with_error)} | {mismatch} | {int(_sum(rows, 'residue'))} "
                f"| {int(_sum(rows, 'unintended'))} | {int(_sum(rows, 'guessed_turns'))}/{int(_sum(rows, 'empty_gt_turns'))} "
                f"| {tokens:.0f} | {_sum(rows, 'wall_seconds') / n:.0f} |")
        lines.append("")
        if "steward" in systems:
            for other in sorted(set(systems) - {"steward"}):
                for repeat in sorted(set(systems["steward"]) & set(systems[other])):
                    mine = {r["id"]: int(r["passed"]) for r in systems["steward"][repeat]}
                    theirs = {r["id"]: int(r["passed"]) for r in systems[other][repeat]}
                    ids = sorted(mine.keys() & theirs.keys())
                    a, b, p = mcnemar([mine[i] for i in ids], [theirs[i] for i in ids])
                    lines.append(f"- steward vs {other}, repeat {repeat}: only steward {a}, only {other} {b}, "
                                 f"exact McNemar p = {p:.3f} (n = {len(ids)})")
            lines.append("")
    target.write_text("\n".join(lines) + "\n")
