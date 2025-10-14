# Changelog

## Unreleased
- Added `scripts/check_dependency_compatibility.py` and supporting
  documentation for dependency compatibility audits (`docs/COMPATIBILITY_AUDIT.md`).

## v0.7.0
- **Command Room:** SCOUT recon, SUSTAIN dials, SUPPLY narratives, microchip rows for top symbol.
- **Recon CLI:** `--mode {prob|micro}`, `--include-supply`, `--pretty`, optional `chips_summary` in JSON.
- **Sustainment:** new dials `sustainability` / `fakeout_risk`.
- **Alerts/Notify:** optional supply/sustainment enrichment (env gated).
- **IBKR Adapter:** live daily features with TTL cache; health tracking.
- **Tests:** 120+ tests, high coverage on chips/probability/aggregation.

## v0.6.x
- Runtime driver, loop, profiles: budget + cooldown, panel stubs.

(earlier releases omitted)
