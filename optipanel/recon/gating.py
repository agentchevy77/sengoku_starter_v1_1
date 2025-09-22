from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from optipanel.chips.aggregate import compute_sustainment
from optipanel.chips.runtime import chips_by_tf_for_snapshot
from optipanel.recon.readiness import readiness_from_front_sustain
from optipanel.setups.engine import compute_setups


def _accepted_from_verdicts(v: Mapping[str, Any]) -> bool:
    if not isinstance(v, Mapping):
        return False

    for key in ("D", "H1", "M15"):
        val = v.get(key)
        if isinstance(val, str) and val.lower().startswith("confirm"):
            return True
        if isinstance(val, Mapping):
            st = str(val.get("status", "")).lower()
            if st.startswith("confirm"):
                return True

    summ = v.get("summary")
    if isinstance(summ, str) and summ.lower().startswith("confirm"):
        return True
    if isinstance(summ, Mapping):
        for node in summ.values():
            if isinstance(node, Mapping):
                st = str(node.get("status", "")).lower()
                if st.startswith("confirm"):
                    return True
    return False


def _acceptance_verdicts_for_snapshot(snap: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from optipanel.acceptance.engine import verdict_by_tf as _verdict
    except Exception:
        try:
            from optipanel.acceptance.engine import acceptance_by_tf as _verdict
        except Exception:
            _verdict = None

    if _verdict is None:
        return {}
    try:
        return _verdict(snap)
    except Exception:
        return {}


def compute_gate_for_snapshot(
    snap: Mapping[str, Any],
    *,
    ready_min: int = 65,
    armed_floor: int = 50,
) -> dict[str, Any]:
    chips = chips_by_tf_for_snapshot(snap)
    sustain = snap.get("sustainment") if isinstance(snap, Mapping) else None
    if sustain is None:
        try:
            sustain = compute_sustainment(chips)
        except Exception:
            sustain = None
    acceptance_summary = snap.get("acceptance") if isinstance(snap, Mapping) else None
    acceptance_score = None
    if isinstance(acceptance_summary, Mapping):
        summary = acceptance_summary.get("summary")
        if isinstance(summary, Mapping):
            acceptance_score = summary.get("score")
    front_units = snap.get("setups") if isinstance(snap, Mapping) else None
    if not isinstance(front_units, Mapping):
        feats = snap.get("features_top") or snap.get("features") or {}
        try:
            front_units = compute_setups(dict(feats) if isinstance(feats, Mapping) else {})
        except Exception:
            front_units = {}
    readiness_data = readiness_from_front_sustain(
        front_units,
        sustain,
        acceptance=acceptance_score,
    )
    attack = readiness_data.get("attack", 0)
    defense = readiness_data.get("defense", 0)
    readiness = int(max(0, min(100, (attack + defense) / 2)))

    verdicts = _acceptance_verdicts_for_snapshot(snap)
    accepted = _accepted_from_verdicts(verdicts)

    if accepted and readiness >= ready_min:
        state = "go"
    elif readiness >= max(armed_floor, ready_min - 15):
        state = "armed"
    else:
        state = "hold"

    return {
        "accepted": bool(accepted),
        "readiness": readiness,
        "state": state,
        "details": {
            "ready_min": int(ready_min),
            "armed_floor": int(armed_floor),
            "verdicts": verdicts,
            "attack": attack,
            "defense": defense,
        },
    }
