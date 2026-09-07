#!/usr/bin/env python3
"""
Steward: runnable baseline.

Runs the stock BFCL V4 multi-turn agent loop over a small slice of
`multi_turn_base` and reports how often it leaves the simulated system in the
correct final state. This is the baseline the project aims to beat.

    python run_baseline.py                    # 20 cases, 6-20 min
    python run_baseline.py --limit 5          # smoke test
    python run_baseline.py --analyze-only     # score an existing run, no API

Individual multi-turn cases run 30-65 tool calls sequentially, so the slowest
case gates the run whatever the thread count, and wall-clock time swings with
endpoint load: a measured 20-case run took 6.2 min at ten threads, while a
3-case run during development took 7.8 min. For a no-API-key reproduction of
the full 200-case baseline in under a second, use analyze_failures.py.

Results land in  <bfcl>/capstone_run/{result,score}/  so a run can never
overwrite the cached full-benchmark artifacts.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "qwen3-235b-a22b-instruct-2507"
CATEGORY = "multi_turn_base"
RUN_ROOT = "capstone_run"          # relative to the BFCL project root
IDS_FILE = "test_case_ids_to_generate.json"


def find_bfcl_root(explicit=None):
    """Locate the berkeley-function-call-leaderboard checkout."""
    candidates = [
        explicit,
        os.environ.get("BFCL_HOME"),
        HERE.parent / "gorilla" / "berkeley-function-call-leaderboard",
        HERE / "gorilla" / "berkeley-function-call-leaderboard",
    ]
    for c in candidates:
        if c and (Path(c) / "bfcl_eval").is_dir():
            return Path(c).resolve()
    sys.exit(
        "error: could not find the BFCL checkout.\n"
        "  Run ./setup.sh first, or set BFCL_HOME=/path/to/"
        "berkeley-function-call-leaderboard"
    )


def bfcl_python(root):
    """Prefer the venv interpreter created by setup.sh."""
    venv = root / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def check_env(root):
    """Verify the endpoint credentials are present before spending time."""
    env_file = root / ".env"
    have = bool(os.environ.get("QWEN_API_KEY"))
    if not have and env_file.exists():
        have = any(
            line.strip().startswith("QWEN_API_KEY=") and line.strip() != "QWEN_API_KEY="
            for line in env_file.read_text().splitlines()
        )
    if not have:
        sys.exit(
            f"error: QWEN_API_KEY is not set.\n"
            f"  Add it to {env_file} along with:\n"
            f"    QWEN_BASE_URL=https://openai.rc.asu.edu/v1\n"
            f"  See README.md, section 'Configuration'."
        )


def write_ids(root, ids):
    """Point --run-ids at our slice, preserving whatever was there before."""
    path = root / IDS_FILE
    backup = None
    if path.exists():
        backup = path.with_suffix(".json.capstone-backup")
        shutil.copy2(path, backup)
    path.write_text(json.dumps({CATEGORY: ids}, indent=2))
    return backup


def restore_ids(root, backup):
    path = root / IDS_FILE
    if backup and backup.exists():
        shutil.move(str(backup), str(path))
    elif path.exists():
        path.unlink()


def run(cmd, cwd, env):
    print(f"\n$ {' '.join(cmd)}\n", flush=True)
    proc = subprocess.run(cmd, cwd=cwd, env=env)
    return proc.returncode


def score_path(root):
    return root / RUN_ROOT / "score" / MODEL / "multi_turn" / f"BFCL_v4_{CATEGORY}_score.json"


def summarize(root, ids):
    """Print the headline number from the score file this run produced."""
    path = score_path(root)
    if not path.exists():
        print(f"\nwarning: no score file at {path}", file=sys.stderr)
        return None

    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    summary = rows[0]
    failures = rows[1:]

    acc = summary.get("accuracy", 0.0)
    correct = summary.get("correct_count", 0)
    total = summary.get("total_count", 0)

    print()
    print("=" * 72)
    print(f"BASELINE RESULT: {CATEGORY}  ({total} cases)")
    print("=" * 72)
    print(f"  model    : {MODEL} (Prompt mode)")
    print(f"  accuracy : {acc * 100:.2f}%   ({correct}/{total} left the system in the correct state)")
    print(f"  failures : {len(failures)}")
    if failures:
        print()
        print("  failing cases:")
        for r in failures:
            kind = r["error"]["error_type"].replace("multi_turn:", "")
            print(f"    {r['id']:<26} {kind}")
    print()
    print(f"  score file : {path}")
    print("=" * 72)
    print()
    print("Next:")
    print(f"  python analyze_failures.py --score {path}")
    print(f"  python analyze_failures.py --case {failures[0]['id']}" if failures else "")
    return acc


def main():
    p = argparse.ArgumentParser(description="Run the BFCL multi-turn baseline.")
    p.add_argument("--limit", type=int, default=20,
                   help="number of multi_turn_base cases to run (default: 20)")
    p.add_argument("--ids", help="comma-separated case ids, overrides --limit")
    p.add_argument("--threads", type=int, default=10,
                   help="concurrent requests (default: 10; lower if the endpoint 5xxs)")
    p.add_argument("--bfcl-home", help="path to berkeley-function-call-leaderboard")
    p.add_argument("--analyze-only", action="store_true",
                   help="skip generation, just score/report an existing run")
    args = p.parse_args()

    root = find_bfcl_root(args.bfcl_home)
    py = bfcl_python(root)
    env = {**os.environ, "BFCL_PROJECT_ROOT": str(root)}

    ids = ([s.strip() for s in args.ids.split(",") if s.strip()] if args.ids
           else [f"{CATEGORY}_{i}" for i in range(args.limit)])

    print(f"BFCL root : {root}")
    print(f"python    : {py}")
    print(f"cases     : {len(ids)}  ({ids[0]} .. {ids[-1]})")

    if not args.analyze_only:
        check_env(root)
        started = time.time()
        backup = write_ids(root, ids)
        try:
            rc = run([py, "-m", "bfcl_eval", "generate",
                      "--model", MODEL,
                      "--run-ids",
                      "--num-threads", str(args.threads),
                      "--result-dir", f"{RUN_ROOT}/result",
                      "-o"], cwd=root, env=env)
            if rc != 0:
                sys.exit(f"error: generation failed (exit {rc})")
        finally:
            restore_ids(root, backup)
        print(f"\ngeneration finished in {(time.time() - started) / 60:.1f} min")

    rc = run([py, "-m", "bfcl_eval", "evaluate",
              "--model", MODEL,
              "--test-category", CATEGORY,
              "--result-dir", f"{RUN_ROOT}/result",
              "--score-dir", f"{RUN_ROOT}/score",
              "--partial-eval"], cwd=root, env=env)
    if rc != 0:
        sys.exit(f"error: evaluation failed (exit {rc})")

    summarize(root, ids)


if __name__ == "__main__":
    main()
