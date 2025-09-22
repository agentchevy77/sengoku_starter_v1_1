from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from optipanel.chips.runtime import chips_by_tf_for_snapshot
from optipanel.readiness.engine import compute_readiness


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
    readiness = int(compute_readiness(chips))

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
        },
    }
