#!/usr/bin/env bash
set -euo pipefail

SYMS="${1:-AAPL,MSFT,SPY}"
PYTHON_BIN=${PYTHON_BIN:-python3}

CLI="${PYTHON_BIN} -m optipanel.cli.main"

echo "== Health =="
${CLI} health --ping || true

echo
echo "== Recon (pretty) =="
${CLI} recon --symbols "$SYMS" --provider tws-live --pretty --include-supply || true

echo
echo "== Recon (json) =="
${CLI} recon --symbols "$SYMS" --provider tws-live --json-include chips_summary --include-supply || true

echo
echo "== Command Room sample =="
${PYTHON_BIN} - <<'PY'
from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room

symbols = "AAPL,MSFT,SPY".split(",")
fetcher = RealTwsFetcher(cfg_from_env())
features = fetcher.features_for_symbols(symbols)
tick = run_once({sym: features.get(sym, {}) for sym in symbols})
print(render_command_room(tick, width=24, top_n=2))
PY
