# WO-RECON-02 — Recon Source Unification

**Goal**
Use probability chips (“prob”) as the canonical signal for recon outputs, with microchips acting as secondary scout context only.

**Allowed paths**
- `optipanel/chips/compute.py`
- `optipanel/recon/enrich.py`
- `optipanel/ui/command_room.py`
- `tests/test_prob_tf.py`
- `tests/test_recon_enrich.py`
- `tests/test_command_room.py`

**Tasks**
1. Update `compute_chips_by_tf` so `mode="prob"` remains default and micro-derived probabilities never override the prob values.
2. `build_recon_entry` should always base `agg/recon/sustainment` on prob chips; microchips only populate supply/debug sections.
3. Command Room display should label micro rows explicitly as “SCOUT” data and keep prob chips as the main numeric values.

**Definition of Done**
- `pytest -q` passes.
- Recon JSON shows identical `agg/recon/sustainment` whether or not micro mode is requested.
- Command Room retains prob chip blocks and includes micro scout rows with clear labeling.
