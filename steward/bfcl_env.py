"""Locate the BFCL checkout and load its .env before bfcl_eval is imported."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BFCL = Path(os.environ.get("BFCL_HOME", ROOT.parent / "gorilla" / "berkeley-function-call-leaderboard"))
os.environ.setdefault("BFCL_PROJECT_ROOT", str(BFCL))

env_file = BFCL / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))
