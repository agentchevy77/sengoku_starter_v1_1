# Command Room Panel Layout

The `sengoku command-room` CLI prints the tactical panel in the sequence below. All sections render for the highest-ranked symbol (TOP #1) first, followed by subsequent symbols when `--top-n > 1`.

1. **Banner** — `=== COMMAND ROOM (LIVE) ===`
2. **Advice meter** — `advice: attack=## defend=## standby=##`
3. **TOP line** — comma-separated list of monitored symbols
4. **Battlefield block** — ASCII bars representing front-unit intensity for the current symbol
5. **Recon lines** (beneath battlefield block for the top symbol):
   - `SCOUT     recon [###]` — composite recon score
   - `SUSTAIN  sustain=###  fakeout=###` — sustainment dials (0–100)
   - `READY    attack=###  defense=###` — readiness meters (attack/defense)
6. **Microchips (top symbol)**
   - `micro M15 donchian=.. trend_dma=.. support_def=.. res_clear=.. rvol=.. rs=.. vwap=..`
   - `micro H1  …`
   - `micro D1  …`
7. **SUPPLY narratives** *(optional)* — one line per front-unit highlight, e.g.
   - `SUPPLY breakout_up ⇐ donchian_M15, res_clear_M15, rs_H1`
   - `SUPPLY trend_long ⇐ trend_dma_D1, rs_H1, vwap_D1`
8. **Acceptance / alerts summary** — acceptance flag line (if armed/confirmed) and alert counts.

> SUPPLY narrative factors are described in detail in [RECON_ALERTS_SUPPLY](RECON_ALERTS_SUPPLY.md).

All numeric readings are 0–100 integers. READY lines surface the same readiness meters shipped with recon JSON/alerts.

These recon, sustain, ready, supply, and micro lines render directly beneath the battlefield unit grid for the most actionable symbol.

## UI & API access

- **Textual cockpit** — run `python -m optipanel.ui.textual.app` after installing `.[ui]` extras to see the live Command Room layout in the terminal.
- **FastAPI gateway** — run `python -m optipanel.api.app` (requires `.[web]` extras) and query `GET /watchlist` or `GET /recon/{symbol}` for the same data in JSON form.
