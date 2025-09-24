# WO-UI-WEB-01 — Textual Cockpit & FastAPI Gateway Prototype

## Objective
Deliver a playable prototype that showcases the Sengoku "command room" inside a
Textual-powered TUI while exposing the same data feeds via a FastAPI gateway.

## Branch & Environment
- Suggested branch name: `feature/textual-fastapi-prototype`.
- Activate a fresh virtual environment and install the new bundles:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  python -m pip install -e .[ui,web,async,caching]
  ```

## Work Breakdown
1. **Baseline Metrics**
   - Capture current ASCII CLI latency for `sengoku recon` and `sengoku notify`.
   - Record CPU and memory via `pytest-benchmark` or `time`.

2. **Textual TUI Shell**
   - Create `optipanel/ui/textual/app.py` with panels mirroring COMMAND ROOM,
     SCOUT, SUPPLY, etc.
   - Stream data via existing runtime hooks; emit metrics through `json_utils`.

3. **FastAPI Gateway**
   - Add `optipanel/api/app.py` exposing `/recon`, `/notify`, and `/metrics`
     endpoints.
   - Use `uvicorn` for local dev (`uvicorn optipanel.api.app:app --reload`).

4. **Shared Service Layer**
   - Refactor common data-fetch helpers into `optipanel/runtime/service.py` so
     both the TUI and FastAPI paths reuse the same async functions.

5. **Performance Comparison**
   - Run the new Textual UI and FastAPI endpoints under load; capture before vs.
     after latency and throughput.
   - Document findings in `docs/UI_FASTAPI_PROTOTYPE.md`.

6. **Exit Criteria**
   - Textual shell renders live data updates without regressions.
   - FastAPI endpoints return JSON compatible with existing CLI outputs.
   - Metrics demonstrate equal or better latency vs. the legacy CLI.

## Follow-ups
- Add CI jobs for the FastAPI test suite (`pytest -m web`) and Textual smoke
  tests (`pytest tests/ui/test_textual_app.py -m slow`).
- Collaborate with Ops to deploy the gateway behind the existing auth layer.

**Primary test:** `pytest tests/test_app_smoke.py -q`
