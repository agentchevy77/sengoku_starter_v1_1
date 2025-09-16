# WO-SAFE-LEAKS — Memory leak guardrails baseline
Allowed paths: `optipanel/services/leakguard.py`, `optipanel/services/scheduler.py`, `tests/test_leaks.py`, `tests/test_scheduler.py`

Tasks
- Ensure LeakSentinel compares tracemalloc snapshots and fails if growth > 1 MB over cycles.
- Ensure AsyncResourceRegistry tracks and closes all resources on shutdown.
- Verify PeriodicTask stops all asyncio tasks on stop().

DoD
- `pytest -q` passes; no lingering tasks and low memory growth.
