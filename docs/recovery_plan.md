# Recovery Plan (2025-10-08)

We rolled `feature/session-logs` back to commit `b50635c` (2025-10-05) to get off the unstable shim branch. Minimal plumbing was reintroduced so the historical stack loads:

- `optipanel.utils.safe_error_handler` (core SafeErrorHandler implementation)
- `optipanel.utils.error_sanitizer` (Bug #53 CLI sanitiser)
- `safe_int` / `safe_float` helpers re-added to `optipanel/utils/safe_ops.py`

## Current Status (2025-10-12)

- ✅ **Baseline restored:** `SENGOKU_TEST_SCOPE=full pytest -v --tb=short` now reports **835 passed / 12 skipped / 0 failed** with total coverage at **86.4 %**. Verbose mode is required in this environment to avoid buffered output appearing as a hang.
- ✅ **Bucket 1 – Data Integrity / CLI:** JSON serialization and sanitizer regressions corrected (`optipanel/json_utils.py`, `optipanel/utils/error_sanitizer.py`, `optipanel/cli/main.py`, `optipanel/engine/aggregate.py`); targeted tests remain green.
- ✅ **Bucket 2/4 – TWS Integration:** Stabilised fetcher reintroduced with RateLimiter compatibility fixes; Bug #4/43 scenarios remain green (`optipanel/adapters/ibkr/tws_fetcher.py`).
- ✅ **Bucket 3 – Concurrency & UI:** Textual refresh race and background task tracking reinstated (`optipanel/ui/textual/minimal.py`); UI regression suites still passing apart from legacy warning noise.
- ✅ **Bucket 4 – Strategy Computation:** Fresh unit suites now protect `optipanel/setups/engine.py` and `optipanel/engine/aggregate.py`, covering scoring logic, risk penalties, and advice orchestration.

## Proactive Hardening Phase (Dark-Debt Coverage)

The rollback also removed the coverage suites that guarded our high-risk modules. We are rehydrating them in priority order:

1. **Operational Logging** (`tests/test_session_logger_safe.py`) – ✅ restored (skips when POSIX locking is unavailable).
2. **Safety Utilities** (`tests/test_utils_safe_ops.py`) – ✅ restored; 32 test cases passing against current implementation.
3. **Safety Error Handling** (`tests/test_utils_safe_error_handler.py`) – ✅ rewritten for the current API (`max_recursion`, `failure_threshold`, `reset_timeout_seconds`, keyword-only `handle_error_safely`) and passing.
4. **Alerting Engine** (`tests/test_notify_engine_unit.py`) – ✅ restored; suite passes against current implementation.
5. **Strategy Computation** (`tests/test_setups_engine_unit.py`, `tests/test_engine_aggregate_unit.py`) – ✅ new safety nets exercise setup scoring, aggregation, and risk-adjusted advice.

## Next Actions

- Monitor SafeErrorHandler behaviour during broader feature work; registry helpers now document the keyword-only API—update tests if signatures drift again.
- Continue chasing coverage hotspots called out in pytest-cov (`optipanel/utils/time_utils.py`, `optipanel/ops/session_logger_safe.py`, etc.) to move the minimum above 90 % for Tier‑1 modules.
- When running the full baseline in automated contexts, prefer `pytest -v --tb=short` (or set `PYTEST_ADDOPTS`) to avoid buffered output triggering watchdog timeouts.

Keep this document updated as the remaining coverage work lands so future sessions have an accurate checkpoint.

## Daily Updates

### 2025-10-12
- Rebuilt `tests/test_utils_safe_error_handler.py` around the modern SafeErrorHandler API (constructor `max_recursion`, new `CircuitBreakerState` keywords, keyword-only `handle_error_safely`). Suite now passes locally with `PYTEST_ADDOPTS='--no-cov'`.
- Added docstrings clarifying the updated SafeErrorHandler signatures and documented pytest buffering behaviour in `TESTING.md`.
- Full regression baseline green: `751 passed / 12 skipped` in ~23 s with coverage 85.9 %. Remember to run with `-v --tb=short` to stream progress in constrained harnesses.

### 2025-10-11
- Recovered full alerting engine coverage via `tests/test_notify_engine_unit.py` (Parts 1–3), ensuring normalization, indexing, merge logic, and magnitude handling align with the rolled-back API.
- Introduced focused suites for strategy computation (`tests/test_setups_engine_unit.py`, `tests/test_engine_aggregate_unit.py`), mocking external dependencies to exercise scoring, risk penalties, advice gates, and timeframe selection.
- Latest regression run: `835 passed / 12 skipped` in ~22 s, total coverage 86.4 %. Strategy computation dark-debt cleared; roadmap hardening phase complete pending optional coverage enhancements above Tier‑1 targets.
