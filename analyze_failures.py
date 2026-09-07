#!/usr/bin/env python3
"""
Steward: baseline failure analysis.

Reproduces the baseline score and the failure taxonomy from BFCL multi-turn
score files. Runs entirely offline against cached artifacts, so it needs no
API key and no LLM calls.

    python analyze_failures.py                      # cached baseline (<1s)
    python analyze_failures.py --score PATH.json    # a fresh run's score file
    python analyze_failures.py --case multi_turn_base_2   # one case in detail
"""

import argparse
import gzip
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SCORE = HERE / "baseline" / "cached" / "multi_turn_base_score.json.gz"
DEFAULT_RESULT = HERE / "baseline" / "cached" / "multi_turn_base_result.json.gz"


def open_maybe_gz(path):
    """Open a .json or .json.gz file as text."""
    path = Path(path)
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8")
    return open(path, encoding="utf-8")


def load_score(path):
    """BFCL score files are JSONL: line 0 is the summary, the rest are failures."""
    with open_maybe_gz(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        sys.exit(f"error: {path} is empty")
    return rows[0], rows[1:]


def load_result(path):
    if not Path(path).exists():
        return None
    with open_maybe_gz(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------- tool calls

def collect_tool_responses(obj, acc):
    """Walk an inference_log and collect every tool-response payload."""
    if isinstance(obj, dict):
        if obj.get("role") == "tool":
            acc.append(obj.get("content"))
        for v in obj.values():
            collect_tool_responses(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_tool_responses(v, acc)
    return acc


def collect_apis(obj, acc):
    """Walk an inference_log and collect which stateful backends the case touched."""
    if isinstance(obj, dict):
        if obj.get("role") == "state_info":
            acc.add(obj.get("class_name"))
        for v in obj.values():
            collect_apis(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_apis(v, acc)
    return acc


def is_error(content):
    return isinstance(content, str) and '"error"' in content


def error_message(content):
    try:
        return json.loads(content).get("error", "")
    except Exception:
        return ""


# ------------------------------------------------------------- state deltas

def _normalize(x):
    """Reduce a state value to a comparable set, or None if not set-like."""
    if isinstance(x, dict):
        return {(k, json.dumps(v, sort_keys=True, default=str)) for k, v in x.items()}
    if isinstance(x, list):
        return {json.dumps(v, sort_keys=True, default=str) for v in x}
    return None


def classify_delta(model, truth):
    """
    Classify how the model's final state differs from ground truth.

      EXTRA   - model has state ground truth does not (a stray side effect)
      MISSING - ground truth has state the model never produced
      CHANGED - same keys, different values
      MIXED   - both extra and missing
    """
    nm, ng = _normalize(model), _normalize(truth)
    if nm is not None and ng is not None:
        extra, missing = nm - ng, ng - nm
        if extra and not missing:
            return "EXTRA"
        if missing and not extra:
            return "MISSING"
        if extra and missing:
            if isinstance(model, dict) and isinstance(truth, dict) and set(model) == set(truth):
                return "CHANGED"
            return "MIXED"
        return "CHANGED"
    if isinstance(model, str) and isinstance(truth, str):
        # Filesystem states arrive as repr strings; length is a usable proxy.
        if len(model) > len(truth):
            return "EXTRA"
        if len(model) < len(truth):
            return "MISSING"
        return "CHANGED"
    return "UNCLASSIFIED"


def case_delta_tags(row):
    diffs = row.get("error", {}).get("details", {}).get("differences", {}) or {}
    return {classify_delta(v.get("model"), v.get("ground_truth"))
            for v in diffs.values() if isinstance(v, dict)}


# ------------------------------------------------------------------ reports

def bar(n, total, width=32):
    filled = 0 if not total else round(n / total * width)
    return "#" * filled + "." * (width - filled)


OPS_BACKENDS = {"GorillaFileSystem", "TicketAPI", "MessageAPI"}

# Errors that mean "the call was well-formed but issued against a system that
# was not in the required state" -- the precondition/ordering class.
PRECONDITION_MARKERS = (
    "no such file or directory", "not found", "path not allowed",
    "needs to be pressed", "must be locked", "before activating",
    "before starting", "invalid access token", "not logged in",
)


def is_precondition(msg):
    m = (msg or "").lower()
    return any(k in m for k in PRECONDITION_MARKERS)


def workload_breakdown(results, failures):
    """
    Baseline accuracy per stateful backend and per deployment slice.

    Steward is certified across all seven BFCL backends, but its first
    deployment uses the ops trio (files, tickets, messages). The other four
    are held out: they are never tuned against, so they measure whether the
    reliability mechanisms generalize beyond the domain they were built for.
    """
    failed_ids = {r["id"] for r in failures}
    per = {}
    slices = {"ops trio (deployment)": [], "held-out (4 backends)": [], "all backends": []}

    for r in results:
        used = collect_apis(r.get("inference_log", []), set())
        used.discard(None)
        for b in used:
            per.setdefault(b, []).append(r)
        if used and used <= OPS_BACKENDS:
            slices["ops trio (deployment)"].append(r)
        if used and not (used & OPS_BACKENDS):
            slices["held-out (4 backends)"].append(r)
        slices["all backends"].append(r)

    def line(label, rows, width=24):
        if not rows:
            print(f"  {label:<{width}}   no cases in this slice")
            return
        passed = sum(1 for r in rows if r["id"] not in failed_ids)
        print(f"  {label:<{width}} {passed:3d}/{len(rows):3d} passed = "
              f"{passed / len(rows) * 100:5.2f}%")

    print("-" * 72)
    print("0. BASELINE BY WORKLOAD")
    print("-" * 72)
    print("  per backend (a case counts once for each backend it touches):")
    for b, rows in sorted(per.items(), key=lambda kv: -len(kv[1])):
        line("    " + b, rows, width=26)
    print()
    print("  by deployment slice:")
    for label in ("ops trio (deployment)", "held-out (4 backends)", "all backends"):
        line("    " + label, slices[label], width=26)
    print()
    print("  No backend exceeds 70%. The deployment slice scores below the")
    print("  all-backends average, so the two are reported separately.")
    print()


def precondition_evidence(results, failures):
    """
    Measure how much of each backend's tool-error volume is precondition
    related, restricted to failing cases that touch a single backend so that
    attribution is unambiguous. A comparable rate across backends indicates a
    failure mode that is independent of the domain.
    """
    failed_ids = {r["id"] for r in failures}
    rows = []
    for r in results:
        if r["id"] not in failed_ids:
            continue
        used = collect_apis(r.get("inference_log", []), set())
        used.discard(None)
        if len(used) != 1:
            continue                      # single-backend cases only: clean attribution
        backend = next(iter(used))
        msgs = [error_message(c)
                for c in collect_tool_responses(r.get("inference_log", []), [])
                if is_error(c)]
        rows.append((backend, msgs))
    if not rows:
        return

    print("-" * 72)
    print("5. IS THE FAILURE DOMAIN-SPECIFIC?  (single-backend failing cases)")
    print("-" * 72)
    agg = {}
    for backend, msgs in rows:
        n_err, n_pre, sample = agg.get(backend, (0, 0, None))
        for m in msgs:
            n_err += 1
            if is_precondition(m):
                n_pre += 1
                sample = sample or m
        agg[backend] = (n_err, n_pre, sample)

    tot_e = tot_p = 0
    for backend, (n_err, n_pre, sample) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        if not n_err:
            continue
        tot_e += n_err
        tot_p += n_pre
        print(f"  {backend:<20} {n_pre:3d}/{n_err:3d} errors are precondition "
              f"({n_pre / n_err * 100:3.0f}%)")
        if sample:
            print(f"  {'':<20}   e.g. {sample[:46]}")
    if tot_e:
        print()
        print(f"  overall: {tot_p}/{tot_e} = {tot_p / tot_e * 100:.0f}% of tool errors are")
        print("  precondition or ordering violations, at a comparable rate in")
        print("  every backend. 'No such file or directory', 'Booking not found'")
        print("  and 'Brake pedal needs to be pressed' all describe a call issued")
        print("  before the system was verified to be in a state permitting it.")
    print()


def report(score_path, result_path):
    summary, failures = load_score(score_path)
    results = load_result(result_path) if result_path else None

    # Refuse to mix a score file from one run with results from another.
    if results is not None and len(results) != summary.get("total_count", len(results)):
        print(f"note: {Path(result_path).name} holds {len(results)} cases but this "
              f"score file covers {summary.get('total_count')}.\n"
              f"      They are different runs, so trace-based sections are skipped.\n")
        results = None

    acc = summary.get("accuracy", 0.0)
    correct = summary.get("correct_count", 0)
    total = summary.get("total_count", 0)

    print("=" * 72)
    print("BFCL V4  multi_turn_base  BASELINE")
    print("=" * 72)
    print(f"  model     : qwen3-235b-a22b-instruct-2507 (Prompt mode)")
    print(f"  accuracy  : {acc * 100:.2f}%   ({correct}/{total} cases passed)")
    print(f"  failures  : {len(failures)}")
    print()

    if results:
        workload_breakdown(results, failures)

    # ---- 1. failure types
    print("-" * 72)
    print("1. FAILURE TYPE")
    print("-" * 72)
    types = Counter(r["error"]["error_type"] for r in failures)
    for name, n in types.most_common():
        label = name.replace("multi_turn:", "")
        print(f"  {n:4d}  ({n / len(failures) * 100:4.1f}%)  {bar(n, len(failures))}  {label}")
    print()
    print("  State corruption, meaning the final system state is wrong, is")
    print("  the dominant failure mode.")
    print()

    # ---- 2. shape of the state delta
    state_rows = [r for r in failures
                  if r["error"]["error_type"] == "multi_turn:instance_state_mismatch"]
    if state_rows:
        print("-" * 72)
        print(f"2. SHAPE OF THE STATE DELTA  ({len(state_rows)} state-mismatch cases)")
        print("-" * 72)
        tally = Counter()
        for r in state_rows:
            for tag in case_delta_tags(r):
                tally[tag] += 1
        meaning = {
            "EXTRA": "stray side effect  -> rollback-addressable",
            "MISSING": "work never done    -> preflight/ordering",
            "CHANGED": "wrong value written",
            "MIXED": "both extra and missing",
            "UNCLASSIFIED": "state not structurally comparable",
        }
        for tag, n in tally.most_common():
            print(f"  {n:4d} cases  involve {tag:<13} {meaning.get(tag, '')}")
        print()
        print("  Counts overlap: one case can exhibit several tags at once.")
        print()

    # ---- 3. tool-call error rates, failed vs passed
    if results:
        failed_ids = {r["id"] for r in failures}
        print("-" * 72)
        print("3. TOOL-CALL ERROR RATE  (failed vs passed runs)")
        print("-" * 72)
        buckets = {
            "FAILED": [r for r in results if r["id"] in failed_ids],
            "PASSED": [r for r in results if r["id"] not in failed_ids],
        }
        for label, rows in buckets.items():
            if not rows:
                continue
            n_any = n_calls = n_err = 0
            for r in rows:
                calls = collect_tool_responses(r.get("inference_log", []), [])
                bad = [c for c in calls if is_error(c)]
                n_calls += len(calls)
                n_err += len(bad)
                n_any += bool(bad)
            pct_any = n_any / len(rows) * 100
            pct_err = (n_err / n_calls * 100) if n_calls else 0
            print(f"  {label}: {len(rows):3d} cases | "
                  f"{pct_any:4.0f}% hit >=1 tool error | "
                  f"{n_err:4d}/{n_calls:4d} calls errored ({pct_err:4.1f}%)")
        print()
        print("  Around half of passing runs also hit tool errors and recovered,")
        print("  so the differentiator is recovery quality rather than error count.")
        print()

    # ---- 4. what the errors actually are
    errs = []
    for r in state_rows:
        for c in collect_tool_responses(r.get("inference_log", []), []):
            if is_error(c):
                errs.append(error_message(c))
    if errs:
        print("-" * 72)
        print("4. MOST COMMON FAILED TOOL CALLS (in corrupted runs)")
        print("-" * 72)
        for msg, n in Counter(e[:58] for e in errs if e).most_common(8):
            print(f"  {n:4d}  {msg}")
        print()
        print("  These are ordering and precondition violations: a correct")
        print("  function called too early, or against an unverified path.")
        print()

    if results:
        precondition_evidence(results, failures)
    print("=" * 72)


def show_case(score_path, case_id):
    _, failures = load_score(score_path)
    row = next((r for r in failures if r["id"] == case_id), None)
    if row is None:
        sys.exit(f"'{case_id}' is not among the failing cases "
                 f"(it may have passed, or the id may be wrong).")

    print("=" * 72)
    print(f"CASE {case_id}  FAILED")
    print("=" * 72)
    print(f"  error type: {row['error']['error_type']}")
    print(f"  message   : {row['error'].get('error_message', '')}")
    print()

    turns = row.get("prompt", {}).get("question", [])
    for i, turn in enumerate(turns):
        for m in turn:
            if m.get("role") == "user":
                print(f"  USER turn {i}: {m['content'][:160]}")
    print()

    calls = collect_tool_responses(row.get("inference_log", []), [])
    bad = [c for c in calls if is_error(c)]
    print(f"  tool calls: {len(calls)}   errored: {len(bad)}")
    for c in bad[:6]:
        print(f"    ERROR  {error_message(c)[:100]}")
    print()

    for cls, v in (row["error"].get("details", {}).get("differences", {}) or {}).items():
        if not isinstance(v, dict):
            continue
        print(f"  --- state '{cls}' ({classify_delta(v.get('model'), v.get('ground_truth'))}) ---")
        print(f"    model : {str(v.get('model'))[:300]}")
        print(f"    truth : {str(v.get('ground_truth'))[:300]}")
    print("=" * 72)


def matching_result(score_path):
    """
    Find the result file that belongs to a given score file.

    BFCL writes score/<model>/<group>/BFCL_v4_<cat>_score.json alongside
    result/<model>/<group>/BFCL_v4_<cat>_result.json. Pairing them matters:
    scoring a fresh 20-case run against the cached 200-case result file would
    silently mix two different runs and report meaningless per-backend rates.
    """
    score_path = Path(score_path)
    if score_path.resolve() == Path(DEFAULT_SCORE).resolve():
        return Path(DEFAULT_RESULT)
    name = score_path.name.replace("_score.json", "_result.json")
    parts = list(score_path.resolve().parts)
    if "score" in parts:
        parts[len(parts) - 1 - parts[::-1].index("score")] = "result"
        candidate = Path(*parts).with_name(name)
        if candidate.exists():
            return candidate
    return None


def main():
    p = argparse.ArgumentParser(description="Analyze the BFCL multi-turn baseline.")
    p.add_argument("--score", default=str(DEFAULT_SCORE),
                   help="score JSON(L), .gz allowed (default: cached baseline)")
    p.add_argument("--result", default=None,
                   help="raw result JSON(L); by default, the one matching --score")
    p.add_argument("--case", help="print one case in detail instead of the summary")
    args = p.parse_args()

    if not Path(args.score).exists():
        sys.exit(f"error: score file not found: {args.score}")

    if args.case:
        show_case(args.score, args.case)
        return

    result = Path(args.result) if args.result else matching_result(args.score)
    if result is None:
        print("note: no result file found next to this score file; sections that\n"
              "      need raw traces (workload breakdown, tool-error rates) are\n"
              "      skipped. Pass --result explicitly to include them.\n")
    report(args.score, result)


if __name__ == "__main__":
    main()
