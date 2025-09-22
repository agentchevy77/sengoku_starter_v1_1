# Command Room Panel

`optipanel.ui.command_room.render_command_room(run_out, width, top_n)` renders an ASCII snapshot combining battlefield units, recon chips, and new readiness lines. Key sections:

- **Header**: session banner, advice counts, TOP list.
- **Battlefield bars**: TOTAL plus indicator lines (`dma20`, `support`, `resistance`, etc.).
- **Probability chips**: `chips(summary)` followed by `chips(M15)`, `chips(H1)`, `chips(D)`.
- **SCOUT**: `SCOUT     recon [###]` headline score.
- **SUSTAIN**: `SUSTAIN  sustain=###  fakeout=###` continuation vs fakeout dial.
- **READY**: `READY     atk=###  def=###` — readiness meters derived from the same chips and sustainment.
- **SCOUT micro rows**: `SCOUT    M15 ...` `SCOUT    H1 ...` `SCOUT    D1 ...` showing structural microchips.
- **ACCEPT**: `ACCEPT   armed=Y accepted=Y dir=UP` (from acceptance doctrine, when bar data + level present).
- **SUPPLY**: per-front factor list (`SUPPLY   breakout_up ⇐ rvol_H1, vwap_H1, rs_H1`).
- **Alerts**: aggregated counts at the bottom if alerts are present.

You can regenerate the golden snapshot used by tests via `samples/command_room_golden.txt` (see `tests/test_command_room_recorded.py`).
