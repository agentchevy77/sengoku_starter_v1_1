# Legacy Shim Debt Tracker

The following temporary shims were added to keep historical regression suites
passing after the recent refactors. Each item below should receive a dedicated
tech-debt ticket so we can migrate tests to the new APIs and delete the shim.

1. `optipanel.api.app.CacheConfig` – migrate cache tests to `TickCacheSettings` / modern cache wiring.
2. `optipanel.battlefield.units_v2._safe_percentage_change` – update battlefield tests to use decimal helpers.
3. `optipanel.setups.engine._clamp_unit` / `_safe_ratio` – transition setup tests to direct Decimal logic.
4. `optipanel.utils.constants` – replace epsilon imports with `optipanel.utils.decimal_types`.
5. `optipanel.utils.error_sanitizer.ErrorSanitizer` – adopt `SafeErrorHandler` in CLI tests and remove shim.
6. `optipanel.testing.test_scope` – switch to pytest markers for optional test gating.

Each shim module already emits a `DeprecationWarning` to flag accidental new usage.
Plan to close these items incrementally; when a ticket is done, remove the shim
and update this list.

## Ticket Tracking

- `optipanel.api.app.CacheConfig` – Ticket: in progress (tests now target `TickCacheSettings`; shim remains for legacy suites).
- `optipanel.battlefield.units_v2._safe_percentage_change` – Ticket: pending (decimal helper rollout).
- `optipanel.setups.engine._clamp_unit` / `_safe_ratio` – Ticket: pending (Decimal conversion of setups tests).
- `optipanel.utils.constants` – Ticket: pending (replace epsilon imports with decimal types).
- `optipanel.utils.error_sanitizer.ErrorSanitizer` – Ticket: pending (CLI adopts `SafeErrorHandler`).
- `optipanel.testing.test_scope` – Ticket: pending (pytest marker conversion).

## Current Session Status (2025-xx-xx)

- Focused regression suites (`tests/test_bug_57_cache_settings.py`, `tests/test_setups_engine_unit.py`,
  `tests/test_bug_53_error_sanitization.py`) now pass once run without the global
  coverage gate. They still fail under the repository-wide `--cov-fail-under=61`
  setting because the full codebase isn’t exercised in these targeted runs.
- `tests/test_bug_49_threshold_boundary.py` indentation error has been fixed.
- The shims above are wired in and raise `DeprecationWarning`s at import time.
- A local venv (`.venv/`) with `textual` installed is required to run the CLI/UI tests.

### Quick-start checklist for next session

1. Recreate/activate the venv:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install textual
   ```

2. Run focused suites with coverage disabled (global gate otherwise fails):

   ```bash
   PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_bug_57_cache_settings.py -vv
   PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_setups_engine_unit.py -vv
   PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" .venv/bin/pytest tests/test_bug_53_error_sanitization.py -vv
   ```

3. For a full run, drop the override so the repository-level coverage target still enforces 61%.

## Next Recommended Steps

1. For quick spot-checks, override the coverage gate when running individual suites
   (e.g. `PYTEST_ADDOPTS="--no-cov --cov-fail-under=0"`). For full runs, keep the default.
2. Create backlog tickets mirroring each shim item in this document.
3. Migrate one suite at a time to the modern APIs; delete the corresponding shim and
   update this tracker when done.
