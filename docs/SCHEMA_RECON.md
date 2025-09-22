# Recon JSON Schema

The recon CLI (`sengoku recon`) produces a per-symbol JSON payload. Each top-level key is a symbol ticker and maps to a recon entry matching the structure below.

```json
{
  "SYMBOL": {
    "recon": 0..100,
    "agg": { "breakout_up": 62, "trend_long": 72, "rejection_down": 58, "...": "..." },
    "tf": {
      "D":   { "breakout_up": 62, "trend_long": 72, "...": "..." },
      "H1":  { "breakout_up": 60, "trend_long": 68, "...": "..." },
      "M15": { "breakout_up": 55, "trend_long": 65, "...": "..." }
    },
    "sustainment": { "sustainability": 83, "fakeout_risk": 36 },
    "supply": { "breakout_up": ["rvol_H1", "vwap_H1"], "trend_long": ["rvol_H1", "rs_H1"] },
    "chips_summary": {
      "D":   { "position": 62, "momentum": 72, "supply": 58 },
      "H1":  { "position": 61, "momentum": 70, "supply": 56 },
      "M15": { "position": 59, "momentum": 64, "supply": 55 }
    }
  }
}
```

Notes:
- `recon`: headline readiness score (0‒100) derived from probability chips.
- `agg`: aggregated probability-chip intensities across timeframes.
- `tf`: raw probability chips per timeframe (`D`, `H1`, `M15`).
- `sustainment`: continuation vs fakeout readings (0‒100).
- `supply` *(optional)*: readiness factors backing each front (enabled via `--include-supply` or `SENGOKU_RECON_SUPPLY_DEFAULT=1`).
- `chips_summary` *(optional)*: compact position/momentum/supply snapshot per timeframe (enabled via `--json-include chips_summary`).

Validation helper: `optipanel.recon.schemas.validate_recon_entry` performs lightweight checks without external dependencies.
