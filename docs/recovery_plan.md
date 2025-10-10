# Recovery Plan (2025-10-08)

We rolled `feature/session-logs` back to commit `b50635c` (2025-10-05) to get off the unstable shim branch. Minimal plumbing was reintroduced so the historical stack loads:

- `optipanel.utils.safe_error_handler` (core SafeErrorHandler implementation)
- `optipanel.utils.error_sanitizer` (Bug #53 CLI sanitiser)
- `safe_int` / `safe_float` helpers re-added to `optipanel/utils/safe_ops.py`

## Current Status (2025-10-10)

- ⚠️ **Baseline interrupted:** Latest `SENGOKU_TEST_SCOPE=full pytest` run reports **746 passed / 11 skipped / 2 failed / 4 errors**. Failures/errors originate from the restored SafeErrorHandler suite, which currently targets an older API signature.
- ✅ **Bucket 1 – Data Integrity / CLI:** JSON serialization and sanitizer regressions corrected (`optipanel/json_utils.py`, `optipanel/utils/error_sanitizer.py`, `optipanel/cli/main.py`, `optipanel/engine/aggregate.py`); targeted tests remain green.
- ✅ **Bucket 2/4 – TWS Integration:** Stabilised fetcher reintroduced with RateLimiter compatibility fixes; Bug #4/43 scenarios remain green (`optipanel/adapters/ibkr/tws_fetcher.py`).
- ✅ **Bucket 3 – Concurrency & UI:** Textual refresh race and background task tracking reinstated (`optipanel/ui/textual/minimal.py`); UI regression suites still passing apart from legacy warning noise.

## Proactive Hardening Phase (Dark-Debt Coverage)

The rollback also removed the coverage suites that guarded our high-risk modules. We are rehydrating them in priority order:

1. **Operational Logging** (`tests/test_session_logger_safe.py`) – ✅ restored (skips when POSIX locking is unavailable).
2. **Safety Utilities** (`tests/test_utils_safe_ops.py`) – ✅ restored; 32 test cases passing against current implementation.
3. **Safety Error Handling** (`tests/test_utils_safe_error_handler.py`) – ⚠️ restored template but currently failing due to API drift (missing `recursion_limit`/breaker kwargs, changed `CircuitBreakerState` constructor, `handle_error_safely` signature).
4. **Alerting Engine** (`tests/test_notify_engine_unit.py`) – ✅ restored; suite passes against current implementation.

## Next Actions

- Adapt `tests/test_utils_safe_error_handler.py` to the rolled-back SafeErrorHandler API:
  - Update fixture to use supported constructor arguments (e.g., `max_recursion`) and align with current breaker configuration helpers.
  - Adjust `CircuitBreakerState` expectations to new parameter names (`failure_threshold`, `reset_timeout_seconds`).
  - Call `handle_error_safely` using keyword arguments (`handle_error_safely("message", context=..., exc=...)`).
- Once the SafeErrorHandler suite runs clean, re-run `PYTEST_ADDOPTS='--no-cov' pytest tests/test_utils_safe_error_handler.py -vv` followed by the full baseline (`SENGOKU_TEST_SCOPE=full pytest`).
- Monitor remaining coverage items; with SafeErrorHandler back online, confirm overall test counts and update this plan accordingly.

Keep this document updated as the remaining coverage work lands so future sessions have an accurate checkpoint.

## Daily Update (2025-10-10)

- Alerting engine coverage restored via `tests/test_notify_engine_unit.py`; suite passes against current notify engine.
- Historical SafeErrorHandler suite reintroduced (`tests/test_utils_safe_error_handler.py`) and confirmed failing due to API drift, highlighting the remaining dark-debt gap. Failures stem from constructor parameter changes (`max_recursion` vs `recursion_limit`, circuit-breaker config) and the updated `handle_error_safely` signature.
- Next session should align the test fixture and expectations with the present SafeErrorHandler implementation, rerun the targeted suite, then verify `SENGOKU_TEST_SCOPE=full pytest` returns to all-green status (≥746 passed, 0 failed). 
