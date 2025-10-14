# Recon JSON Schema & CLI Contract

Each `sengoku recon` invocation yields a JSON object keyed by symbol. Every symbol entry exposes the following fields:

- `recon` *(int 0–100)* — composite recon score (higher = more favourable setup).
- `agg` *(mapping)* — aggregate probability chips such as `breakout_up_prob`, `trend_long_prob`, `rejection_down_prob`, etc.
- `tf` *(mapping)* — per-timeframe chip blocks for `D`, `H1`, and `M15`; values are 0–100.
- `sustainment` *(mapping, always present)*:
  - `sustainability` *(int 0–100)*
  - `fakeout_risk` *(int 0–100)*
- `readiness` *(mapping, always present)*:
  - `attack` / `defense` *(int 0–100)* — READY meters derived from setups + sustainment + acceptance.
  - `components` *(mapping)* — provenance inputs (`attack_core`, `defense_core`, `sustainability`, `fakeout_risk`, `acceptance`).
- `supply` *(mapping, optional)* — per front-unit narrative, e.g. `{ "breakout_up": ["donchian_M15", "res_clear_M15", "rs_H1"], ... }`.
- `chips_summary` *(mapping, optional)* — compact per-timeframe summary emitted by the aggregator when requested.

> Supply narratives are documented in [RECON_ALERTS_SUPPLY](RECON_ALERTS_SUPPLY.md).

## How to enable optional fields

- CLI flag: `--include-supply` adds SUPPLY narratives to pretty output and JSON.
- Env default: `SENGOKU_RECON_SUPPLY_DEFAULT=1` forces SUPPLY on without the CLI flag.
- JSON summaries: `--json-include chips_summary` appends the `chips_summary` block.

Example invocations:

```bash
# Pretty mode with supply
sengoku recon --symbols AAPL,MSFT --provider tws-live --pretty --include-supply

# JSON with summaries + supply
sengoku recon --symbols AAPL,MSFT --provider tws-live --json-include chips_summary --include-supply

# FastAPI recon detail (after starting python -m optipanel.api.app)
curl "http://localhost:8000/recon/AAPL?include_supply=1"
```
