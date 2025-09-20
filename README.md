# Sengoku Decision Cockpit — Starter (v1.1, memory-safe)

This starter gives you a clean, leak-safe Python backbone plus tests and workorders for your AI team.

Quick start:

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .[dev]
pre-commit install
pytest -q
python -m optipanel.app      # demo scheduler (Ctrl+C to stop)
```

## Live IBKR checks

`profiles-live` now accepts the TWS connection flags directly. Example (replace the host/port/client ID for your setup):

```bash
source .venv/bin/activate
sengoku profiles-live \
  --profiles-yaml config/examples/live_profiles.yaml \
  --provider tws-live \
  --ticks 1 \
  --tws-host 192.168.80.1 \
  --tws-port 7496 \
  --client-id 107
```

Alternatively set `SENGOKU_TWS_HOST`, `SENGOKU_TWS_PORT`, and `SENGOKU_TWS_CLIENT_ID` env vars and skip the flags.
