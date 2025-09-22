# WO-SUPPLY-01 — Supply Lines (Explainability)
**Allowed paths:** `optipanel/**/supply*`, `optipanel/ui/command_room.py`, `tests/**`

**Tasks**
- Given front-units (prob chips) + microchips_by_tf, explain key factors supporting each front signal.
- Render supply lines in Command Room; unit tests verify stable formatting.

**DoD**
- tests/test_supply_explain.py passing.
- Command Room shows "SUPPLY breakout_up ⇐…" etc for the top symbol.
