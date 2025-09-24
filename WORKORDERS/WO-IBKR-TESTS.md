# Workorder: IBKR fetcher test coverage

## Summary
Increase integration safety for IBKR-facing adapters by adding deterministic tests around the network-heavy paths once we have mocks in place.

## Motivation
- `optipanel/adapters/ibkr/tws_fetcher.py` still has low coverage around `features_for_symbols()` because it depends on live TWS sessions.
- `optipanel/adapters/ibkr/sandbox.RealTwsFetcher` mirrors this behaviour and should stay in sync.
- The CLI entry `optipanel/cli/live_positions.py` relies on the same fetcher and currently lacks automated smoke coverage.

## Proposed Tasks
1. Build a reusable fake TWS session:
   - Mimic `_HistApp` callbacks (`historicalData`, `historicalDataEnd`).
   - Drive pacing windows and cache hits without real sockets.
2. Use the stub to unit-test `RealTwsFetcher.features_for_symbols()`:
   - Happy path: multiple symbols, ref symbol inclusion, translator output.
   - Fallback behaviour: stale-cache usage when timeouts/errors occur.
   - Pacing metrics: verify logging happens after fresh requests.
3. Add a sandbox regression test ensuring the stubbed fetcher stays compatible with CLI.
4. Optional: add a Click-based smoke test for `optipanel/cli/live_positions.py` using the fake fetcher.

## Notes
- Reuse the patterns from `tests/test_tws_fetcher_unit.py` as scaffolding.
- Keep the fake lightweight so it runs in CI without external dependencies.
- Coordinate with IBKR integration work to avoid drift between real and stubbed behaviour.

**Primary test:** `pytest tests/test_tws_fetcher_features.py -q`
