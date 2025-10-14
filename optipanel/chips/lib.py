"""Probability chip helpers built on microchip inputs."""

from __future__ import annotations

from typing import Any

from .micro import compute_microchips_m15


def _comp(value: float) -> float:
    return 100.0 - value


def _extremity(value: float) -> float:
    return max(value, 100.0 - value)


def microchips_from_features(features: dict[str, Any]) -> dict[str, int]:
    """Backward-compatible shortcut that returns 15m microchips."""

    return compute_microchips_m15(features)


def probs_from_microchips(micro: dict[str, int]) -> dict[str, int]:
    """Map microchips into standard probability chip keys."""

    don = float(micro.get("donchian", 50))
    trend_dma = float(micro.get("trend_dma", 50))
    support_def = float(micro.get("support_def", 50))
    res_clear = float(micro.get("res_clear", 50))
    rvol = float(micro.get("rvol", 50))
    rs = float(micro.get("rs", 50))
    vwap = float(micro.get("vwap", 50))

    breakout_up = 0.35 * res_clear + 0.20 * rvol + 0.20 * rs + 0.15 * trend_dma + 0.10 * don
    breakdown_down = (
        0.35 * _comp(support_def) + 0.20 * rvol + 0.20 * _comp(rs) + 0.15 * _comp(trend_dma) + 0.10 * _comp(don)
    )
    bounce_up = 0.45 * support_def + 0.15 * _comp(trend_dma) + 0.15 * rs + 0.15 * rvol + 0.10 * _comp(res_clear)
    rejection_down = (
        0.45 * _comp(res_clear) + 0.20 * _comp(trend_dma) + 0.15 * _comp(rs) + 0.10 * rvol + 0.10 * _comp(support_def)
    )
    trend_long = 0.45 * trend_dma + 0.20 * rs + 0.20 * don + 0.10 * vwap + 0.05 * rvol
    trend_short = 0.45 * _comp(trend_dma) + 0.20 * _comp(rs) + 0.20 * _comp(don) + 0.10 * _comp(vwap) + 0.05 * rvol
    exhaustion = 0.35 * max(_extremity(trend_dma), _extremity(don)) + 0.40 * rvol + 0.25 * _extremity(vwap)

    def _clip_int(value: float) -> int:
        value = int(round(value))
        if value < 0:
            return 0
        if value > 100:
            return 100
        return value

    return {
        "breakout_up_prob": _clip_int(breakout_up),
        "breakdown_down_prob": _clip_int(breakdown_down),
        "bounce_up_prob": _clip_int(bounce_up),
        "rejection_down_prob": _clip_int(rejection_down),
        "trend_long_prob": _clip_int(trend_long),
        "trend_short_prob": _clip_int(trend_short),
        "exhaustion_prob": _clip_int(exhaustion),
    }
