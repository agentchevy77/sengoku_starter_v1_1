# WO-SET-01 — Core Setups scoring engine (pure functions)

**Allowed paths (modify only these):**
- `optipanel/setups/__init__.py`
- `optipanel/setups/engine.py`

**Do NOT change tests.** Tests live in `tests/test_setups.py`.

## Tasks
1) Implement `compute_setups(features: dict) -> dict[str, int]` (pure, deterministic; no I/O).
2) Outputs 0..100 for: breakout_up, breakdown_down, bounce_up, rejection_down, trend_long, trend_short, exhaustion.
3) Use last, dma20, support, resistance, rvol, rs_strength, vwap_diff (optional, default 0.0).
4) Heuristics as discussed (near levels + volume + RS + DMA alignment + exhaustion).
5) No dataclasses or config engines. No new dependencies.

## Definition of Done
- `pytest -q` passes.
- Only Allowed paths were changed.
- Pure functions only; no I/O or network; no new deps.
