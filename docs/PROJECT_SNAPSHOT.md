# Project Snapshot (Living Doc)

_Last refreshed: 2025-01-05_

Use this note to keep every session—human or AI—aligned on the current state of
the Sengoku Decision Cockpit. Update the sections below whenever you finish a
sprint, merge a substantial PR, or kick off a new workstream.

## Mission Focus
- Deliver leak-safe, deterministic trading intelligence for single-machine ops.
- Keep recon, alerts, and command room views in sync across CLI/TUI/Web.

## Active Fronts
- **Coverage & Reliability**: Strengthen async scheduler, IBKR adapters, and
  pipeline tests (see: `tests/test_services_scheduler.py`,
  `tests/test_tws_fetcher_features.py`).
- **UI & API Expansion**: WO-UI-WEB-01 (Textual cockpit + FastAPI gateway) is
  queued; scaffolding pending.
- **IBKR Integration**: Follow WO-IBKR-TESTS to maintain parity between sandbox
  and live fetchers.

## Key Modules
- `optipanel/app.py`: async demo runner wiring cache, scheduler, sandbox.
- `optipanel/runtime/loop.py`: pure scan → recon → alert pipeline.
- `optipanel/alerts/engine.py`: threshold-driven alert generation.
- `optipanel/services/`: infrastructure (budget, cache, leakguard, scheduler).
- `optipanel/adapters/ibkr/`: TWS fetchers, sandbox, translators.

## Work Orders & Scope
- Current work orders live under `WORKORDERS/` (e.g., WO-UI-WEB-01). Each PR can
  span multiple WOs; list covered WOs in commit/changelog summaries.
- Respect allowed-path guidance inside every W/O; highlight any deviations in
  PR notes for review.

## Tooling & Commands
- Activate env: `source .venv/bin/activate`
- Format/lint: `pre-commit run --all-files`
- Tests: `pytest -q`
- Coverage threshold: 61% minimum enforced via `pytest-cov`.
- Docs: prefer Markdown in `docs/` and link updates from `CHANGELOG.md` under
  **Unreleased**.

## Recent Highlights
- Added deterministic fake TWS session tests (`tests/test_tws_fetcher_features.py`).
- Extended runtime loop integration coverage (`tests/test_runtime_loop.py`).
- Enabled `pytest-cov` and `pre-commit` hooks by default.
- UI optional dependency bump (`plotext>=6.2.0`).
- Introduced Pydantic v2 configuration models and refactored the loader to validate settings at startup (`optipanel/config/models.py`, `optipanel/config/loader.py`).
- Hardened strategy computation with dedicated setup/aggregate unit suites (`tests/test_setups_engine_unit.py`, `tests/test_engine_aggregate_unit.py`).

## Parking Lot / Follow-ups
- Roll Pydantic models through remaining boundaries (TWS fetcher payloads, alert schemas, feature bundles) to replace ad-hoc dict handling.
- Evaluate adopting Pydantic `field_serializer`/`field_validator` patterns to remove deprecation warnings and lower JSON serialization overhead.
- Implement Textual TUI + FastAPI gateway prototype per WO-UI-WEB-01.
- Add async smoke tests once the new UI/Web layers land.
- Consider richer budget meter telemetry for observability.

_Tip: Reference this snapshot in every PR/hand-off summary to keep the team on
the same page._
