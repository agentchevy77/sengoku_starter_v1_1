# AI Onboarding — How to work on this repo

- One WORKORDER per PR. Modify only the allowed paths listed inside the W/O file.
- Return **unified diffs**. Commentary ≤ 300 words.
- Run `pytest -q` and paste results.
- No new network calls in tests—use the sandbox adapter and fixtures.
- Long-running loops must use `PeriodicTask` and be tracked in `AsyncResourceRegistry`.
- All caches via `TTLCache` with size/TTL bounds; respect `BudgetMeter.backoff_active`.
