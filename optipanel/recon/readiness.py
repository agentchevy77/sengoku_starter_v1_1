from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def _clip(value: float) -> int:
    return max(0, min(100, int(round(value))))


def readiness_from_front_sustain(
    front: Mapping[str, Any] | None,
    sustain: Mapping[str, Any] | None,
    acceptance: Any | None = None,
) -> dict[str, Any]:
    """Compute offensive/defensive readiness with lightweight component debug info."""

    front = front or {}
    sustain = sustain or {}

    sustain_v = _as_int(sustain.get("sustainability"), 50)
    fakeout_v = _as_int(sustain.get("fakeout_risk"), 50)
    acc_v = 50 if acceptance is None else _clip(_as_int(acceptance, 50))

    breakout = _as_int(front.get("breakout_up"))
    trend = _as_int(front.get("trend_long"))
    reject = _as_int(front.get("rejection_down"))
    breakdown = _as_int(front.get("breakdown_down"))

    attack_core = max(breakout, trend)
    defense_core = max(reject, breakdown)

    attack_score = 0.6 * attack_core + 0.3 * sustain_v - 0.2 * fakeout_v + 0.1 * acc_v
    defense_score = 0.6 * defense_core + 0.2 * fakeout_v + 0.2 * (100 - sustain_v) + 0.1 * (100 - acc_v)

    return {
        "attack": _clip(attack_score),
        "defense": _clip(defense_score),
        "components": {
            "attack_core": _clip(attack_core),
            "defense_core": _clip(defense_core),
            "sustainability": _clip(sustain_v),
            "fakeout_risk": _clip(fakeout_v),
            "acceptance": _clip(acc_v),
        },
    }
