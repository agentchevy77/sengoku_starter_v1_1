# Command Room (v0.7)

Order of sections for the top symbol:
1. Header: `=== COMMAND ROOM (LIVE) ===`
2. Advice counts + TOP symbol(s)
3. Battlefield units block (TOTAL + unit bars)
4. `SCOUT     recon [###]`               // composite recon
5. `SUSTAIN   sustain=###  fakeout=###`  // sustainment dials
6. Microchips for top symbol:
   - `micro M15 ...`
   - `micro H1  ...`
   - `micro D1  ...`
7. SUPPLY narratives:
   - `SUPPLY   breakout_up  ⇐ donchian_M15, res_clear_M15, rs_H1`
8. Alerts block with counts by type

Notes:
- All numbers are 0..100 ints.
- Microchips show structural posture; recon uses probability chips.
- Supply lines explain “why” a setup is strong/weak (provenance).
