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

## Quickstart (Recon)

```bash
# Live (IBKR)
export SENGOKU_TWS_HOST=192.168.80.1
export SENGOKU_TWS_PORT=7496
export SENGOKU_TWS_CLIENT_ID=107
sengoku recon --symbols AAPL,MSFT --provider tws-live --pretty --include-supply

# JSON mode with extras
sengoku recon --symbols AAPL,MSFT --provider tws-live --json-include chips_summary --include-supply
sengoku profiles-live --profiles-yaml config/examples/live_profiles.yaml --provider tws-live --ticks 2
```

Environment toggles:

- `SENGOKU_RECON_SUPPLY_DEFAULT=1`
- `SENGOKU_ALERTS_INCLUDE_SUPPLY=1`
- `SENGOKU_NOTIFY_INCLUDE_SUPPLY=1`

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

## Operator cheat-sheet

- [Recon schema reference](docs/SCHEMA_RECON.md) — field-by-field guide to recon JSON payloads.
- [Recon, alerts & supply toggles](docs/RECON_ALERTS_SUPPLY.md) — how to enable supply/sustain and CLI examples.
- [Command Room layout](docs/COMMAND_ROOM.md) — ordering of panel sections and sample lines.
- [Project Snapshot](docs/PROJECT_SNAPSHOT.md) — living doc for mission focus, active work, and quick commands.

## Recon Quickstart

```bash
# Live (IBKR)
export SENGOKU_TWS_HOST=192.168.80.1
export SENGOKU_TWS_PORT=7496
export SENGOKU_TWS_CLIENT_ID=107

sengoku recon --symbols AAPL,MSFT --provider tws-live --pretty --include-supply

# JSON with chips summary
sengoku recon --symbols AAPL,MSFT --provider tws-live --json-include chips_summary
```

Environment toggles:

- `SENGOKU_RECON_SUPPLY_DEFAULT=1`
- `SENGOKU_ALERTS_INCLUDE_SUPPLY=1`
- `SENGOKU_NOTIFY_INCLUDE_SUPPLY=1`
