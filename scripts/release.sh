#!/usr/bin/env bash
set -euo pipefail

VER="${1:-}"
if [[ -z "${VER}" ]]; then
  echo "usage: scripts/release.sh <version>"; exit 1
fi

echo "[1/6] set version=${VER}"
sed -i "s/^version = .*/version = \"${VER}\"/" pyproject.toml

echo "[2/6] tests & lint"
pytest -q
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit run --all-files || true  # allow warnings to display
  pre-commit run --all-files
else
  echo "pre-commit not found; skipping lint step"
fi

echo "[3/6] changelog & tag"
git add -A
git commit -m "chore(release): v${VER}" || true
git tag -a "v${VER}" -m "Sengoku ${VER}"

echo "[4/6] build"
python -m build

if [[ "${PUBLISH:-0}" == "1" ]]; then
  echo "[5/6] upload"
  python -m twine upload dist/*
else
  echo "[5/6] upload skipped (set PUBLISH=1 to enable)"
fi

echo "[6/6] push"
git push
git push --tags

echo "Done. Release v${VER}"
