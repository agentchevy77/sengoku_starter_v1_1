from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def readiness_from_front_sustain(
    front: Mapping[str, int] | None,
    sustain: Mapping[str, Any] | None,
    acceptance: int | None = None,
) -> dict[str, int]:
    front = front or {}
    sustain = sustain or {}

    sustain_v = int(sustain.get("sustainability", 50))
    fakeout_v = int(sustain.get("fakeout_risk", 50))
    acc_v = 50 if acceptance is None else int(acceptance)

    breakout = int(front.get("breakout_up", 0))
    trend = int(front.get("trend_long", 0))
    reject = int(front.get("rejection_down", 0))
    breakdown = int(front.get("breakdown_down", 0))

    attack = 0.6 * max(breakout, trend) + 0.3 * sustain_v - 0.2 * fakeout_v + 0.1 * acc_v
    defense = 0.6 * max(reject, breakdown) + 0.2 * fakeout_v + 0.2 * (100 - sustain_v) + 0.1 * (100 - acc_v)

    def _clip(value: float) -> int:
        return max(0, min(100, int(round(value))))

    return {"attack": _clip(attack), "defense": _clip(defense)}
