# WO-BF-UI-GLUE — Battlefield UI glue (panel + recon)

**Status: COMPLETE**

## Scope
- Keep Command Room panel behavior (probability chips, microchips for top symbol, SUPPLY lines).
- Add CLI "recon --pretty" mode:
  - Per-symbol header
  - SCOUT recon [###] (aggregate via aggregate_chips + recon_score)
  - SUPPLY narratives (via explain_supply(front_units, micro_chips_by_tf))
  - Optional one-line probability chip summary per timeframe

## Allowed paths
- optipanel/cli/main.py
- tests/test_cli_recon.py
- WORKORDERS/WO-BF-UI-GLUE.md

## Definition of Done
- pytest -q all green
- `sengoku recon --symbols AAPL,MSFT --provider tws-live --pretty` prints SCOUT and SUPPLY lines
- `sengoku recon --provider mock --features-yaml <file> --pretty` prints same narratives
- No regressions to Command Room tests
