#!/usr/bin/env bash
# Steward: one-shot environment setup.
#
#   ./setup.sh
#
# Clones the BFCL checkout, creates a Python 3.11 venv, installs the package,
# and applies the patches needed to run against a vLLM-served endpoint.
# Safe to re-run: each step is skipped if already done.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GORILLA_DIR="${BFCL_PARENT:-$(dirname "$HERE")}/gorilla"
LB_DIR="$GORILLA_DIR/berkeley-function-call-leaderboard"
PINNED_COMMIT="6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"

echo "==> BFCL checkout"
if [ ! -d "$LB_DIR" ]; then
  git clone https://github.com/ShishirPatil/gorilla.git "$GORILLA_DIR"
  git -C "$GORILLA_DIR" checkout "$PINNED_COMMIT"
else
  echo "    already present: $LB_DIR"
fi

echo "==> Python 3.11 venv"
cd "$LB_DIR"
if [ ! -d .venv ]; then
  # BFCL requires >=3.10; macOS system Python is often 3.9.
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.11 .venv
  else
    python3.11 -m venv .venv 2>/dev/null \
      || { echo "error: need Python 3.11 (or install 'uv')"; exit 1; }
  fi
else
  echo "    already present: $LB_DIR/.venv"
fi

echo "==> install bfcl_eval"
# 'soundfile' is imported by qwen-agent but not declared as a dependency,
# so 'bfcl --help' crashes without it.
if command -v uv >/dev/null 2>&1; then
  VIRTUAL_ENV="$LB_DIR/.venv" uv pip install -e . soundfile
else
  ./.venv/bin/pip install -q -e . soundfile
fi

echo "==> patch the Qwen handler for vLLM"
# Upstream's handler is written against Alibaba DashScope. Against a vLLM
# server it crashes on zero-argument tool calls and on streaming usage
# accounting (40/3641 cases in our full run).
PATCH="$HERE/patches/qwen_vllm_fix.patch"
TARGET="bfcl_eval/model_handler/api_inference/qwen.py"
if patch -p0 --dry-run --forward --silent "$TARGET" < "$PATCH" >/dev/null 2>&1; then
  patch -p0 --forward "$TARGET" < "$PATCH"
  echo "    patch applied"
else
  echo "    already patched (or does not apply cleanly), skipping"
fi

echo "==> .env"
if [ ! -f .env ]; then
  cat > .env <<'EOF'
# ASU Voyager OpenAI-compatible endpoint (free for ASU students)
QWEN_API_KEY=
QWEN_BASE_URL=https://openai.rc.asu.edu/v1
EOF
  echo "    created $LB_DIR/.env, add your QWEN_API_KEY"
else
  echo "    already present: $LB_DIR/.env"
fi

cat <<EOF

Setup complete.

  BFCL root : $LB_DIR
  next      : add QWEN_API_KEY to $LB_DIR/.env

  then:
    python analyze_failures.py          # no API key needed, <1s
    python run_baseline.py --limit 20   # live run, ~15-20 min
EOF
