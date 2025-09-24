#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-python3}
EXTRAS=(async ui web trading caching typing testing profiling docs ibkr)

cd "$ROOT_DIR"

printf '\n[dependency-smoke] Using %s at %s\n' "$PYTHON" "$(command -v "$PYTHON")"

# Ensure the packaging toolchain is modern enough for editable installs with extras.
"$PYTHON" -m pip install --upgrade pip setuptools wheel

# Install the project once with the full extras set so dependency resolution is shared.
FULL_SET=()
for extra in "${EXTRAS[@]}"; do
  if [ "$extra" != "ibkr" ]; then
    FULL_SET+=("$extra")
  fi
done
FULL_EXTRAS=$(IFS=,; echo "${FULL_SET[*]}")
"$PYTHON" -m pip install -e ".[${FULL_EXTRAS}]"

# Re-run installs per extra to catch metadata or optional dependencies that may be
# guarded by environment markers.
for extra in "${EXTRAS[@]}"; do
  printf '\n[dependency-smoke] Validating extra: %s\n' "$extra"
  if ! "$PYTHON" -m pip install -e ".[${extra}]"; then
    if [ "$extra" = "ibkr" ]; then
      printf '[dependency-smoke] WARN: ibapi wheel not available on public PyPI.\n'
      printf '                      Please install from an internal mirror or vendor package.\n'
      continue
    fi
    printf '[dependency-smoke] ERROR: installation failed for extra %s.\n' "$extra"
    exit 1
  fi
done

# Verify the environment is consistent.
if ! OUTPUT=$("$PYTHON" -m pip check 2>&1); then
  if printf '%s' "$OUTPUT" | grep -q 'safety-schemas'; then
    printf '[dependency-smoke] WARN: Ignore safety/pydantic constraint mismatch (known false positive).\n'
  else
    printf '%s\n' "$OUTPUT"
    exit 1
  fi
fi

# Enforce the documented minimum versions.
"$PYTHON" -m optipanel.ops.dependency_guard --include-dev --strict

printf '\n[dependency-smoke] Completed successfully.\n'
