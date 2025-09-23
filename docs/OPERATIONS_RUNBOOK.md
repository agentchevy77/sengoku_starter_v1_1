# Operations Runbook (Sengoku v0.7.0)

## Prereqs
- TWS running, API enabled, live port 7496 (set `SENGOKU_TWS_PORT` if you must target paper 7497), “Allow connections from localhost” ON.
- Windows Firewall inbound rule for the TWS port from WSL host (or your host subnet).
- In WSL: export `SENGOKU_TWS_HOST`, `SENGOKU_TWS_PORT`, `SENGOKU_TWS_CLIENT_ID`, `SENGOKU_TWS_REF`.

## Health
```bash
python -m optipanel.cli.main health --ping
sengoku recon --symbols AAPL,MSFT,SPY --provider tws-live --pretty --include-supply
python - <<'PY'
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room
print(render_command_room(run_once({"AAPL": {}, "MSFT": {}, "SPY": {}}), width=24, top_n=2))
PY
```

## Troubleshooting

- If health shows `ok: false`, check TWS settings, firewall, and environment variables.
- If daily bars are stale, run `f.clear_cache()` (developer console) to force a refresh.
