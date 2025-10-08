# Coverage Roadmap Progress (Bookmark)

_Last updated: 2025-10-08 05:27:41Z_

This document captures where we left off while hardening the alert ingestion
and aggregation pipeline so we can resume the effort seamlessly next session.

## Completed Work

- **Pydantic market-data models:** Added `optipanel/models/market_data.py` with
  `BaseFeatureBundle` (sparse) and `ValidatedFeatureBundle` (strict) plus
  `convert_to_decimal`. Refactored the aggregation engine to load timeframe
  bundles through these models and added the dedicated unit suite in
  `tests/test_engine_aggregate_unit.py`.
- **Alert payload validation:** Introduced `optipanel/models/alert.py` and
  `optipanel/notify/utils.py`, updated `optipanel/notify/engine.py` to consume
  the parsed models, and adjusted `tests/test_notify_engine_unit.py` alongside
  the new `tests/test_alert_model_unit.py` to cover the validation pipeline.
- **Alert bus compatibility layer:** Restored legacy helpers in
  `optipanel/notify/engine.py`, wrapped bus entries in `AlertEvent` to retain
  both sanitised and raw values for magnitude logic, and verified optional
  fields only persist when present (see `tests/test_bug_63_type_coercion.py`,
  `tests/test_bug_82_magnitude_exception.py`).
- **Regression coverage additions:** Added unit coverage for the `AlertEvent`
  raw/sanitised access pattern (`tests/test_notify_engine_unit.py`) and CLI
  supply toggling (`tests/test_notify_supply.py`) to ensure the new behaviour
  stays locked in.
- All focused suites currently pass via:
  - `PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_alert_model_unit.py -vv`
  - `PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_notify_engine_unit.py -vv`
  - `PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_engine_aggregate_unit.py -vv`
  - `pytest` (1567 passed / 140 skipped / 1 xfailed)

## Next Focus Area

- **End-to-end alert ingestion:** Wire the Pydantic alert model through any
  remaining call sites (CLI utilities, integrations) and add smoke tests that
  feed mixed alert batches through `aggregate_alerts` to confirm the runtime
  behaviour matches the unit expectations.
- **Backfill regression coverage:** Add integration tests (or contract tests)
  around the API layer that consumes `build_symbol_snapshot` to ensure
  `ValidatedFeatureBundle` enforcement does not regress external consumers.
- **Shim repayment sequencing:** Cache shim removed (`CacheConfig` deleted; `TickCacheSettings` is the sole API). Continue retiring remaining legacy helpers per `docs/legacy_shim_debt.md`.

## Suggested Starting Point When Resuming

1. Confirm no remaining modules bypass the new alert/market data models; if
   they do, schedule targeted refactors.
2. Draft integration tests that exercise the snapshot API/CLI end-to-end using
   sanitized fixtures.
3. Document the new models and their fallbacks so future work can adopt them
   consistently.
4. Re-run the focused suites listed above before resuming implementation.

## Outstanding Questions / Notes

- Confirm whether additional integration tests (e.g. covering interactions with
  other modules) are desired after unit coverage is in place.
- Consider capturing logs in tests to assert expected warnings whenever
  coercion occurs (string payload, non-iterable alerts, etc.).
- CLI smoke: `notify_cmd` run with `include_supply` toggled on/off (2025-10-08)
  confirmed no residual `supply` keys leak when the flag is disabled and that
  raw payloads still drive magnitude ordering via `AlertEvent`.
- `_open_secure_append` currently ignores the `flags` argument supplied by
  `Path.open(..., opener=...)`; OR the opener-provided flags with our security
  defaults when we revisit the health monitor.
- Temporary compatibility shims were added for legacy regression suites (see `docs/legacy_shim_debt.md`),
  with DeprecationWarnings and a repayment plan to migrate tests to the modern APIs.

Keep this file updated as progress continues.

## Pre-commit Status

- `pre-commit run --all-files` currently fails because the default cache
  directory (`/home/computrex/.cache/pre-commit/`) is read-only in this
  environment. No hooks ran and no files were modified.
- When resuming, either skip the hook or set `PRE_COMMIT_HOME` to a writable
  location (e.g. `PRE_COMMIT_HOME=$PWD/.pre-commit-cache pre-commit run --all-files`).
