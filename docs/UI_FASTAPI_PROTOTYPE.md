# Textual & FastAPI Prototype Runbook

This runbook tracks latency baselines and future improvements as we migrate the
Sengoku cockpit to Textual and split data feeds through a FastAPI gateway.

## Baseline

1. Activate the development environment with UI/Web extras:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -e .[ui,web,async,caching]
   ```
2. Run the baseline capture script:
   ```bash
   scripts/capture_latency_baseline.py --repeats 5
   ```
3. Commit the resulting `reports/latency-baseline.json` (or archive it in the
   performance dashboard) before implementing the new UI.

## Prototype Tasks

See `WORKORDERS/WO-UI-WEB-01.md` for the detailed branch plan covering:
- Textual TUI shell mirroring COMMAND ROOM/SCOUT/SUPPLY panels.
- FastAPI gateway exposing `/recon`, `/notify`, `/metrics` endpoints.
- Shared async service layer to keep logic in sync across UIs.

## Post-Prototype

1. Capture the new latency numbers with the same script (use `--output` to write
   to a different file, e.g. `reports/latency-prototype.json`).
2. Compare before/after totals and record findings here plus in the release
   notes.
3. Feed the data into Grafana or the ops dashboard for ongoing monitoring.
