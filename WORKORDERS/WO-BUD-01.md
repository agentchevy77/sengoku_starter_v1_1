# WO-BUD-01 — Market Data Budget (meter + soft cap + back-off) — skeleton
Allowed paths: `optipanel/services/budget.py`, `optipanel/app.py`, `tests/test_budget.py`

Tasks
- Implement a budget meter that tracks 'lines' for streams, snapshots, rt-bars.
- Soft cap: if usage >= cap, set `backoff_active=True` and expose a flag.
- Provide a simple event/callback or method clients can poll in tests.

DoD
- Tests simulate usage crossing the cap -> backoff; cooldown clears it.

**Primary test:** `pytest tests/test_budget.py -q`
