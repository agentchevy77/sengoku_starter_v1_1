#!/usr/bin/env bash
set -euo pipefail

echo "[checks] unit tests"
pytest -q

echo "[checks] style"
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit run --all-files
else
  echo "[checks] pre-commit not found; skipping"
fi

echo "[checks] recon schema sanity"
python - <<'PY'
import json, sys
from pathlib import Path
schema = Path("docs/SCHEMA/recon.schema.json")
print("schema present:", schema.exists())
PY

echo "[checks] legacy logger guard"
python3 scripts/check_legacy_logger_usage.py --quiet --minutes 1440
