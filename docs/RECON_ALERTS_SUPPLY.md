# Recon JSON Schema

```json
{
  "SYMBOL": {
    "recon": 0..100,
    "agg": { "...prob fields..." },
    "tf":  { "D": {...}, "H1": {...}, "M15": {...} },
    "sustainment": { "sustainability": 0..100, "fakeout_risk": 0..100 },
    "supply": { "breakout_up": ["..."], "trend_long": ["..."] }   // optional
  }
}
```

## Feature toggles

Defaults keep payloads minimal. Enable extras only when needed:

- `SENGOKU_ALERTS_INCLUDE_SUPPLY=1` — add `supply` blocks to alerts output.
- `SENGOKU_NOTIFY_INCLUDE_SUPPLY=1` or CLI `--include-supply` — enrich notify payloads with supply lines.
- `SENGOKU_RECON_SUPPLY_DEFAULT=1` — include recon supply by default (still overridable with `--include-supply`).
- `--json-include chips_summary` — append per-timeframe `chips_summary` to recon JSON.

## Usage examples

```bash
# Pretty recon with supply & sustain
sengoku recon --symbols AAPL,MSFT --provider tws-live --pretty --include-supply

# JSON recon with chips_summary
sengoku recon --symbols AAPL,MSFT --provider tws-live --json-include chips_summary

# Notify with supply enrichment (opt-in)
SENGOKU_NOTIFY_INCLUDE_SUPPLY=1 sengoku notify --symbols-json '{"AAPL":{}}'
```
