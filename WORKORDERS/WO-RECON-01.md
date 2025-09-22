# WO-RECON-01 — Recon Score & Aggregation
**Allowed paths:** `optipanel/chips/**`, `optipanel/prob/**`, `optipanel/ui/command_room.py`, `tests/**`

**Tasks**
- Aggregate per-TF chips into a composite recon vector and scalar (0..100).
- Expose recon in Command Room and (optionally) CLI.

**DoD**
- Unit tests cover aggregate + recon_score.
- Command Room shows SCOUT recon line.
