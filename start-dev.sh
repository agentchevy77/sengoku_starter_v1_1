#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENVDIR="$ROOT_DIR/.venv"

if [ ! -d "$VENVDIR" ]; then
  python3 -m venv "$VENVDIR"
fi

# shellcheck source=/dev/null
source "$VENVDIR/bin/activate"

pip install --upgrade pip
pip install -e .[dev]

PRE_COMMIT_BIN="$VENVDIR/bin/pre-commit"
if [ -x "$PRE_COMMIT_BIN" ]; then
  PRE_COMMIT_HOME="$ROOT_DIR/.pre-commit-cache" "$PRE_COMMIT_BIN" install
touch "$ROOT_DIR/.pre-commit-cache/.keep"
fi

cat <<'MSG'
Environment ready!
Run commands inside this shell:
  source .venv/bin/activate
Key tooling:
  pytest -q                 # run tests
  black --line-length 120 . # format code
  ruff check --fix .        # lint with autofix
See TESTING.md for full guidelines.
MSG
