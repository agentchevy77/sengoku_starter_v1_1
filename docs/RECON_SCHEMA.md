# Recon JSON schema

The recon pipeline returns one entry per symbol with canonical fields. Only sustainment is always present; other blocks are opt-in.

## Fields

- `recon` *(int 0..100)* — composite recon score.
- `agg` *(object)* — aggregated probability chips (keys like `breakout_up_prob`).
- `tf` *(object)* — per-timeframe probability chips keyed by `D` (daily), `H1`, `M15`.
- `sustainment` *(object)* — continuation diagnostics with `sustainability` and `fakeout_risk`.
- `supply` *(object, optional)* — supply-line factors per front unit.
- `chips_summary` *(object, optional)* — condensed per-timeframe summary (requires `--json-include chips_summary`).
- `tf_scout` *(object, optional)* — structural microchip context when requested.
- `readiness` *(object)* — readiness meters containing `attack`, `defense`, decision `state` (`GO`, `ARM`, `DEF`, `HOLD`), plus `accepted_up`/`accepted_down` flags.

## Example

```json
{
  "AAPL": {
    "recon": 74,
    "agg": {
      "breakout_up_prob": 68,
      "breakdown_down_prob": 32,
      "trend_long_prob": 76,
      "trend_short_prob": 24
    },
    "tf": {
      "D":  {
        "breakout_up_prob": 62,
        "trend_long_prob": 70,
        "trend_short_prob": 30
      },
      "H1": {
        "breakout_up_prob": 69,
        "trend_long_prob": 78
      },
      "M15": {
        "breakout_up_prob": 72,
        "trend_long_prob": 80
      }
    },
    "sustainment": {
      "sustainability": 83,
      "fakeout_risk": 36
    },
    "readiness": {
      "attack": 82,
      "defense": 26,
      "state": "ARM",
      "accepted_up": false,
      "accepted_down": false
    },
    "supply": {
      "breakout_up": ["donchian_M15", "rs_H1"],
      "trend_long":  ["trend_dma_D", "vwap_H1"]
    }
  }
}
```

See [docs/RECON_ALERTS_SUPPLY.md](RECON_ALERTS_SUPPLY.md) for feature toggles and CLI usage.
