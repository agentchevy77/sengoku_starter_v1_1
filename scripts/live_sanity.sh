#!/usr/bin/env bash
set -euo pipefail
: "${SENGOKU_TWS_HOST:=127.0.0.1}"
: "${SENGOKU_TWS_PORT:=7496}"
: "${SENGOKU_TWS_CLIENT_ID:=107}"
: "${SENGOKU_TWS_REF:=SPY}"
: "${SENGOKU_LOG_DIR:=./runs}"

echo "== TWS handshake =="
python - <<'PY'
from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
from optipanel.ops.health import collect_health, write_health
import os

fetcher = RealTwsFetcher(cfg_from_env())
health = collect_health(fetcher)
print(health)
write_health(os.path.join(os.getenv("SENGOKU_LOG_DIR", "./runs"), "health.json"), health)
PY

echo "== Recon (pretty) for PRIME list =="
SYMS="${1:-AAPL,MSFT,SPY}"
SENGOKU_LOG_DIR="${SENGOKU_LOG_DIR}" \
  python -m optipanel.cli.main recon \
    --provider tws-live \
    --symbols "${SYMS}" \
    --pretty --include-supply
