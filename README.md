# Sengoku Decision Cockpit — Starter (v1.1, memory-safe)

> Last snapshot refresh: see `docs/PROJECT_SNAPSHOT.md` (2025-01-05)
>
> Snapshot upkeep: refresh that timestamp after meaningful changes or a green `pytest` run.

This starter gives you a clean, leak-safe Python backbone plus tests and workorders for your AI team.

Quick start:

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .[dev]
pre-commit install
pytest -q
python -m optipanel.app --help  # sanity check CLI wiring
```

Optional demo runner: `python -m optipanel.app` (Ctrl+C to stop).

## Architecture Cheatsheet

<details>
<summary>Click to expand the core component map</summary>

```
           +--------------------+
           |  External Inputs   |
           | (YAML, CLI args)   |
           +----------+---------+
                      |
                      v
+---------------------+---------------------+
|       Runtime & Pipeline Core             |
|  optipanel.runtime.loop / driver.py       |
|  orchestrates scan -> recon -> alerts     |
+---------------------+---------------------+
                      |
        +-------------+-------------+
        |                           |
        v                           v
+---------------+         +-------------------+
|   Services    |         |     Adapters      |
| (cache,       |         |  (IBKR, sandbox)  |
| budget,       |         |                   |
| leakguard)    |         +---------+---------+
+---------------+                   |
        |                           v
        v                 +-----------------------+
+---------------+         |   CLI / Notify / UI   |
| Monitoring &  |         |  (optipanel.cli, ui)  |
| Telemetry     |         +-----------------------+
+---------------+
```

Use this map to align work orders with the subsystems they affect.

</details>

## Textual Command Room UI

Install the UI extras (`pip install -e .[ui]`) and launch the terminal cockpit:

```bash
python -m optipanel.ui.textual.app --profiles-yaml config/examples/live_profiles.yaml \
    --features-yaml config/examples/features.yaml --provider mock --tick-interval 5
```

Controls in the header let you switch provider, adjust the refresh cadence, and
change the top-N focus. Use `r` to trigger an immediate refresh; configure
IBKR credentials before switching to `--provider tws-live`.

Need a leaner view? Swap in `python -m optipanel.ui.textual.minimal` for a
single-panel Command Room poller with pause/refresh hotkeys (`space`, `r`).
Prefer the consolidated CLI? `sengoku tui --profiles-yaml ...` wraps the same
minimal UI behind the main entrypoint.

## FastAPI Gateway

Install the web extras (`pip install -e .[web]`) and start the JSON API:

```bash
python -m optipanel.api.app --profiles-yaml config/examples/live_profiles.yaml \
    --features-yaml config/examples/features.yaml --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health` — readiness probe.
- `GET /watchlist?top=3` — ranked recon panels for the active watchlist.
- `GET /recon/{symbol}` — detail block for a symbol (battlefield text, recon, readiness, supply).
- `GET /metrics` — summary counts, average recon, and budget status.

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
