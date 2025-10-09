# Recovery Plan (2025-10-08)

We rolled `feature/session-logs` back to commit `b50635c` (2025-10-05) to get off the unstable shim branch. Minimal plumbing was reintroduced so the historical stack loads:

- `optipanel.utils.safe_error_handler` (core SafeErrorHandler implementation)
- `optipanel.utils.error_sanitizer` (Bug #53 CLI sanitiser)
- `safe_int` / `safe_float` helpers re-added to `optipanel/utils/safe_ops.py`

With those pieces in place the test tree executes, but the following suites fail against this baseline:

1. **CLI JSON / Driver tests** (`tests/test_cli_json_errors.py`, `tests/test_driver.py`, `tests/test_runtime_loop.py`) – now raise `TypeError: Type is not JSON serializable`. Investigate `optipanel/cli/main.py` and reapply the JSON error-handling fixes that existed on later commits.
2. **TWS error-code classification** (`tests/test_bug_43_tws_error_codes.py`) – log level assertions no longer match. Revisit the Bug #43 commit to restore the log routing.
3. **Textual refresh race** (`tests/test_textual_race_condition.py`) – the background-task leak is unfixed. Cherry-pick the Bug #62 fix or refactor the test.
4. **TWS fetcher/cache regression suites** (`tests/test_tws_fetcher_features.py`, `tests/test_tws_fetcher_unit.py`) – expect the cache migration (`TickCacheSettings`). Either bring those commits forward (0cacfe4 + 029a184) or adapt the tests to the older cache config.

## Suggested Next Steps

- Decide which fixes to cherry-pick from newer history vs. re-implement locally. Start with the CLI JSON serialization errors (Item #1) since they unblock multiple suites.
- If the preference is to reapply the cache migration, cherry-pick `0cacfe4` (“Migrate cache regression to TickCacheSettings”) followed by `029a184` (“Remove CacheConfig shim”) once the CLI fixes are in place.
- For the Textual race test, reapply the Bug #62 fix (`3e1f155`/`f768a62`) or adjust the test to match the simplified scheduler.
- Keep notes here as we land each fix so future sessions can pick up the queue quickly.
