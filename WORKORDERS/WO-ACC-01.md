# WO-ACC-01 — Acceptance Doctrine (two-bar confirmation)

**Allowed paths:**
- `optipanel/acceptance/engine.py`
- `optipanel/ui/command_room.py`
- `tests/test_acceptance_engine.py`
- `tests/test_command_room.py`

**Tasks:**
- Implement `detect_breakout_acceptance(bars, level)` returning `{"armed": bool, "accepted": bool, "debug": {...}}`.
- Armed when price closes beyond the breakout level (above resistance or below support).
- Accepted when, within the next 1–2 bars, price retests the level on lower volume and rejects back in the breakout direction.
- Surface the result in the command-room panel for the top symbol: `ACCEPT armed=X accepted=Y`.

**Acceptance criteria:**
- Unit tests cover:
  1. Clean breakout + low-volume retest ⇒ accepted.
  2. Breakout + high-volume failure ⇒ rejected.
  3. Range-bound ⇒ not armed.
- Command room test asserts the ACCEPT line is rendered for symbols with bar data.
- `pytest -q` passes.
