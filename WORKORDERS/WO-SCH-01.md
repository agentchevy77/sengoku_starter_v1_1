# WO-SCH-01 — Prime/Secondary schedulers (skeleton)
Allowed paths: `optipanel/services/scheduler.py`, `optipanel/services/cache.py`, `optipanel/adapters/ibkr/**`, `optipanel/app.py`, `tests/test_scheduler.py`

Tasks
- Implement periodic jobs: `prime_tick()` (every 5s) and `secondary_thin_tick()` (every 10s) using the sandbox adapter.
- Use TTLCache to store snapshots with TTLs; verify expirations in tests.
- Ensure all jobs can be cleanly cancelled with `await scheduler.stop()`.

DoD
- Tests pass; no orphan tasks; TTL expirations verified.

**Primary test:** `pytest tests/test_scheduler.py -q`
