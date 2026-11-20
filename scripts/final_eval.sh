#!/usr/bin/env bash
# Final evaluation, in the order given in docs/final-plan.md (phase 7).
#
#   scripts/final_eval.sh            # everything; safe to re-run, finished cases are skipped
#   STEP=steward scripts/final_eval.sh   # one step: check, archive, freeze, steward, march,
#                                        # baselines, score, judge, summary
#
# Needs a working QWEN_API_KEY in the BFCL checkout's .env. About 1,400 case runs, roughly
# 5 to 6 hours with 10 workers on the shared endpoint.
#
# Baselines (B0, B1, B2) do not use any Steward mechanism, so their Milestone 2 runs on D1, D2
# and the first repeat of D1h and D3 are kept and only the missing repeats and new sets are run.
# Steward changed, so all of its Milestone 2 outputs are moved to runs/milestone2/ and re-run.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
PY="${PY:-$HERE/../gorilla/berkeley-function-call-leaderboard/.venv/bin/python}"
export PYTHONPATH="$HERE"
THREADS="${THREADS:-10}"
STEP="${STEP:-all}"
MAIN=steward_norollback

step() { [ "$STEP" = all ] || [ "$STEP" = "$1" ]; }

if step check; then
  echo "==> offline tests and guard replay"
  "$PY" tests/test_mechanisms.py
  "$PY" scripts/guard_replay.py --datasets d1,d2,d3,d4,d5 | grep "ground-truth calls blocked"
  "$PY" - <<'EOF'
from steward import bfcl_env  # noqa: F401
import os, openai
client = openai.OpenAI(api_key=os.environ["QWEN_API_KEY"], base_url=os.environ["QWEN_BASE_URL"], timeout=60)
client.chat.completions.create(model="qwen3-235b-a22b-instruct-2507",
                               messages=[{"role": "user", "content": "ok"}], max_tokens=2)
print("endpoint reachable")
EOF
fi

if step archive; then
  echo "==> move Milestone 2 Steward outputs to runs/milestone2/"
  for kind in raw scored judged; do
    for f in runs/$kind/*/steward*; do
      [ -e "$f" ] || continue
      dest="runs/milestone2/$kind/$(basename "$(dirname "$f")")"
      mkdir -p "$dest"
      mv "$f" "$dest/"
    done
  done
  [ -f runs/judged/hand_check_sample.jsonl ] && cp runs/judged/hand_check_sample.jsonl runs/milestone2/judged/
  [ -f runs/summary.md ] && cp runs/summary.md runs/milestone2/summary.md
  [ -f runs/code_freeze.txt ] && cp runs/code_freeze.txt runs/milestone2/code_freeze.txt
fi

if step freeze; then
  echo "==> code freeze record"
  { git rev-parse HEAD; shasum -a 256 steward/*.py; } > runs/code_freeze.txt
  cat runs/code_freeze.txt
fi

run() { "$PY" -m steward.evaluate run --threads "$THREADS" "$@"; }

if step steward; then
  echo "==> Steward on every set, three repeats"
  run --datasets d4,d2,d1,d1h,d3,d5 --systems $MAIN --repeats 0,1,2
fi

if step march; then
  echo "==> the March request, 20 repeats"
  run --datasets march --systems $MAIN --repeats "$(seq 0 19 | paste -sd, -)"
fi

if step baselines; then
  echo "==> baselines: new sets and missing repeats"
  run --datasets d4,d5 --systems b0,b1,b2 --repeats 0,1,2
  run --datasets d1h,d3 --systems b0,b1,b2 --repeats 1,2
fi

if step score; then
  "$PY" -m steward.evaluate score
fi

if step judge; then
  "$PY" -m steward.judge
fi

if step summary; then
  "$PY" -m steward.evaluate summary > /dev/null
  echo "==> written runs/summary.md"
  echo "March request complete in: $(awk -F, 'NR>1 {s+=$2; n++} END {print s "/" n}' runs/scored/march/*.csv 2>/dev/null)"
fi
