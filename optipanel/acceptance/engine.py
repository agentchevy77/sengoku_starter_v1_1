from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _as_float(bar: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = bar.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_bars(bars: Iterable[Mapping[str, Any]]) -> list[dict[str, float]]:
    normalized: list[dict[str, float]] = []
    for bar in bars:
        if not isinstance(bar, Mapping):
            continue
        normalized.append(
            {
                "open": _as_float(bar, "open"),
                "high": _as_float(bar, "high"),
                "low": _as_float(bar, "low"),
                "close": _as_float(bar, "close"),
                "volume": max(0.0, _as_float(bar, "volume")),
            }
        )
    return normalized


def detect_breakout_acceptance(
    bars: Sequence[Mapping[str, Any]] | None,
    level: float | None,
    *,
    tolerance: float = 0.001,
    volume_ratio: float = 0.9,
) -> dict[str, Any]:
    """Detect breakout acceptance using the two-bar confirmation doctrine."""

    debug: dict[str, Any] = {"level": level, "tolerance": tolerance, "volume_ratio": volume_ratio}
    if not bars or level is None:
        return {"armed": False, "accepted": False, "debug": debug}

    data = _normalize_bars(bars)
    if len(data) < 2:
        return {"armed": False, "accepted": False, "debug": debug}

    level = float(level)
    epsilon = max(abs(level) * tolerance, 0.01)

    last = data[-1]
    if last["close"] > level + epsilon:
        direction = "up"
    elif last["close"] < level - epsilon:
        direction = "down"
    else:
        debug.update({"direction": None})
        return {"armed": False, "accepted": False, "debug": debug}

    debug.update({"direction": direction})

    breakout_idx = None
    for idx in range(len(data) - 1, 0, -1):
        close = data[idx]["close"]
        prev_close = data[idx - 1]["close"]
        rel_curr = close - level
        rel_prev = prev_close - level
        if direction == "up":
            if rel_curr > epsilon and rel_prev <= -epsilon:
                breakout_idx = idx
                break
        else:
            if rel_curr < -epsilon and rel_prev >= epsilon:
                breakout_idx = idx
                break
    if breakout_idx is None:
        debug.update({"reason": "no_breakout_cross"})
        return {"armed": False, "accepted": False, "debug": debug}

    breakout_bar = data[breakout_idx]
    breakout_volume = breakout_bar["volume"]

    debug.update(
        {
            "breakout_idx": breakout_idx,
            "breakout_close": breakout_bar["close"],
            "breakout_volume": breakout_volume,
        }
    )

    armed = True
    accepted = False
    retest_idx = None
    for idx in range(breakout_idx + 1, min(len(data), breakout_idx + 3)):
        bar = data[idx]
        volume = bar["volume"]
        if direction == "up":
            touched = bar["low"] <= level + epsilon
            reject = bar["close"] > level + epsilon / 2.0
        else:
            touched = bar["high"] >= level - epsilon
            reject = bar["close"] < level - epsilon / 2.0

        vol_ok = volume <= breakout_volume * volume_ratio if breakout_volume > 0 else True
        debug.setdefault("retests", []).append(
            {
                "index": idx,
                "touched": touched,
                "reject": reject,
                "volume": volume,
                "vol_ok": vol_ok,
            }
        )
        if touched and reject and vol_ok:
            accepted = True
            retest_idx = idx
            break

    debug.update({"retest_idx": retest_idx})
    return {"armed": armed, "accepted": accepted, "debug": debug}
