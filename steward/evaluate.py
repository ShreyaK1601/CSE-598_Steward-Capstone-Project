#!/usr/bin/env python3
"""Run and score the comparison. Scoring uses BFCL's own multi-turn evaluator unchanged.

    python -m steward.evaluate run --datasets d1 --systems b0,b1,b2,steward --repeats 0,1,2
    python -m steward.evaluate score
    python -m steward.evaluate summary
"""

import argparse
import csv
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

from steward import bfcl_env  # noqa: F401
from bfcl_eval.eval_checker.eval_runner import _evaluate_single_multi_turn_entry
from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call

from steward import agent, probes, specs, stats, triage
from steward.dataset import DATASETS

RUNS = bfcl_env.ROOT / "runs"
BASE_SEED = 1000


def result_path(dataset, system, repeat):
    return RUNS / "raw" / dataset / f"{system}_r{repeat}.jsonl"


def done_ids(path):
    if not path.exists():
        return set()
    with open(path) as f:
        return {json.loads(line)["id"] for line in f if line.strip()}


def run_case(entry, dataset, system, repeat, path, lock):
    name = f"{dataset}_{system}_r{repeat}"
    started = time.time()
    try:
        handler = agent.make_handler(system, name, BASE_SEED + repeat)
        responses, meta = handler.inference_multi_turn_prompting(deepcopy(entry), False, True)
    except Exception:
        print(f"[infra] {name} {entry['id']}\n{traceback.format_exc()}", flush=True)
        return False
    row = {"id": entry["id"], "result": responses, "wall_time": time.time() - started, **meta}
    with lock:
        with open(path, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
    return True


def cmd_run(args):
    jobs = []
    lock = threading.Lock()
    for dataset in args.datasets.split(","):
        entries, _ = DATASETS[dataset]()
        for system in args.systems.split(","):
            for repeat in (int(r) for r in args.repeats.split(",")):
                path = result_path(dataset, system, repeat)
                path.parent.mkdir(parents=True, exist_ok=True)
                seen = done_ids(path)
                for entry in entries:
                    if entry["id"] in seen:
                        continue
                    if args.ids and entry["id"] not in args.ids.split(","):
                        continue
                    jobs.append((entry, dataset, system, repeat, path, lock))
    print(f"{len(jobs)} cases to run", flush=True)
    started = time.time()
    with ThreadPoolExecutor(args.threads) as pool:
        outcomes = list(pool.map(lambda job: run_case(*job), jobs))
    print(f"finished {sum(outcomes)}/{len(jobs)} in {(time.time() - started) / 60:.1f} min", flush=True)


class _Decoder(agent.ReliableHandler):
    """Only used for decoding; never contacts the endpoint."""


def _replay(entry, responses, run_name, decoder):
    """Re-execute the logged calls on fresh backends to count calls and read final state."""
    config, classes = entry["initial_config"], entry["involved_classes"]
    _, instances = execute_multi_turn_func_call([], config, classes, run_name, entry["id"])
    calls, errors, mutating_by_turn = 0, 0, []
    for turn in responses:
        mutating = 0
        for step in turn:
            try:
                decoded = decoder.decode_execute(step, has_tool_call_tag=False)
            except Exception:
                continue
            if not decoded or multi_turn_utils.is_empty_execute_response(decoded):
                continue
            results, instances = execute_multi_turn_func_call(
                decoded, config, classes, run_name, entry["id"])
            calls += len(decoded)
            errors += sum(triage.is_error(r) for r in results)
            for call, result in zip(decoded, results):
                name, _, _ = specs.parse_call(call, instances)
                if name in specs.MUTATING and not triage.is_error(result):
                    mutating += 1
        mutating_by_turn.append(mutating)
    return calls, errors, mutating_by_turn, probes.snapshot(instances)


def _truth_state(entry, truth, run_name):
    config, classes = entry["initial_config"], entry["involved_classes"]
    _, instances = execute_multi_turn_func_call([], config, classes, run_name, entry["id"])
    for turn in truth:
        _, instances = execute_multi_turn_func_call(turn, config, classes, run_name, entry["id"])
    return probes.snapshot(instances)


def _purge(prefix):
    space = vars(multi_turn_utils)
    for key in [k for k in space if k.startswith(prefix)]:
        del space[key]


def score_case(row, entry, truth, tag, decoder):
    _purge(tag)
    calls, errors, mutating, final = _replay(entry, row["result"], f"{tag}_replay", decoder)
    target = _truth_state(entry, truth, f"{tag}_truth")
    _, start_instances = execute_multi_turn_func_call(
        [], entry["initial_config"], entry["involved_classes"], f"{tag}_start", entry["id"])
    start = probes.snapshot(start_instances)
    verdict = _evaluate_single_multi_turn_entry(
        decoder, entry["id"], row["result"], truth, deepcopy(entry), f"{tag}_eval", "multi_turn")

    # Files only: pre-existing data that the correct run keeps and this run lost or changed,
    # and items this run left behind that the correct run does not have.
    fs_final = final.get("GorillaFileSystem", {})
    fs_truth = target.get("GorillaFileSystem", {})
    fs_start = start.get("GorillaFileSystem", {})
    unintended = [p for p, v in fs_start.items()
                  if fs_truth.get(p, "\0") == v and fs_final.get(p, "\0") != v]
    residue = [p for p in fs_final if p not in fs_truth and p not in fs_start]

    empty_turns = [i for i, t in enumerate(truth) if not t]
    guessed = sum(1 for i in empty_turns if i < len(mutating) and mutating[i] > 0)

    extra = row.get("steward", {})
    run_stats = extra.get("stats", {})
    reports = extra.get("reports", [])
    return {
        "id": entry["id"],
        "passed": int(bool(verdict["valid"])),
        "error_type": verdict.get("error", {}).get("error_type", "") if not verdict["valid"] else "",
        "tool_calls": calls,
        "tool_errors": errors,
        "blocked": run_stats.get("blocked", 0),
        "skipped": run_stats.get("skipped", 0),
        "probes": run_stats.get("probes", 0),
        "repairs": run_stats.get("repairs", 0),
        "rollbacks": run_stats.get("rollbacks", 0),
        "input_tokens": sum(map(sum, row["input_token_count"])) + run_stats.get("planner_input_tokens", 0),
        "output_tokens": sum(map(sum, row["output_token_count"])) + run_stats.get("planner_output_tokens", 0),
        "llm_seconds": round(sum(map(sum, row["latency"])), 2),
        "wall_seconds": round(row.get("wall_time", 0), 2),
        "unintended": len(unintended),
        "residue": len(residue),
        "empty_gt_turns": len(empty_turns),
        "guessed_turns": guessed,
        "verdicts": "|".join(r.get("verdict", "") for r in reports),
    }


def cmd_score(_args):
    decoder = _Decoder("score_decoder")
    out = RUNS / "scored"
    out.mkdir(parents=True, exist_ok=True)
    for dataset_dir in sorted((RUNS / "raw").iterdir()):
        dataset = dataset_dir.name
        entries, truth = DATASETS[dataset]()
        by_id = {e["id"]: e for e in entries}
        for path in sorted(dataset_dir.glob("*.jsonl")):
            rows = [json.loads(line) for line in open(path) if line.strip()]
            scored = []
            for row in rows:
                tag = f"score_{dataset}_{path.stem}_{row['id']}"
                scored.append(score_case(row, by_id[row["id"]], truth[row["id"]], tag, decoder))
                _purge(tag)
            target = out / dataset / f"{path.stem}.csv"
            target.parent.mkdir(exist_ok=True)
            with open(target, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(scored[0]))
                writer.writeheader()
                writer.writerows(sorted(scored, key=lambda r: int(r["id"].rsplit("_", 1)[1])))
            print(f"{dataset} {path.stem}: {sum(r['passed'] for r in scored)}/{len(scored)}")


def cmd_summary(_args):
    stats.write_summary(RUNS / "scored", RUNS / "summary.md")
    print((RUNS / "summary.md").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--datasets", default="d1")
    run.add_argument("--systems", default="b0,b1,b2,steward")
    run.add_argument("--repeats", default="0")
    run.add_argument("--threads", type=int, default=8)
    run.add_argument("--ids", default="")
    run.set_defaults(func=cmd_run)
    sub.add_parser("score").set_defaults(func=cmd_score)
    sub.add_parser("summary").set_defaults(func=cmd_summary)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
