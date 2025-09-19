#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

current_branch="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$current_branch" == "master" ]]; then
  read -rp "New feature branch name (without prefix): " feature
  if [[ -z "$feature" ]]; then
    echo "Aborting: branch name required"
    exit 1
  fi
  branch="feature/${feature}"
  git switch -c "$branch"
  echo "Switched to $branch"
else
  echo "Already on branch $current_branch"
fi

echo "
Recent commits:\n"

git log --oneline --decorate -5

echo "
Current status:\n"

git status -sb

echo "
Suggested checks:
  ./start-dev.sh           # ensure env/tooling
  source .venv/bin/activate
  pytest -q
  ruff check --fix .
  black <files>
"
