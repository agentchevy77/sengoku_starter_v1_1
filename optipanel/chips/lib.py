"""Shared helpers for lightweight timeframe chip calculations."""

from __future__ import annotations

from typing import Any


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _to_int01(value: float) -> int:
    return int(round(_clamp01(value) * 100))


def _pct_gap_above(last: float, level: float) -> float:
    if last <= 0:
        return 1e9
    return (level - last) / last


def _pct_gap_below(last: float, level: float) -> float:
    if last <= 0:
        return 1e9
    return (last - level) / last


def _comp(value: float) -> float:
    return 100.0 - value


def _extremity(value: float) -> float:
    return max(value, 100.0 - value)


def microchips_from_features(features: dict[str, Any]) -> dict[str, int]:
    """Convert raw features into microchips in the 0..100 range."""

    last = float(features.get("last", 0.0))
    dma20 = float(features.get("dma20", 0.0))
    support = float(features.get("support", 0.0))
    resistance = float(features.get("resistance", 0.0))
    rvol = float(features.get("rvol", 1.0))
    rs_strength = float(features.get("rs_strength", 0.0))
    vwap_diff = float(features.get("vwap_diff", 0.0))

    span = max(1e-9, resistance - support)
    donchian_pos = _clamp01((last - support) / span)

    rel_dma = (last - dma20) / max(1e-9, last)
    trend_dma = _clamp01(0.5 + rel_dma / 0.10)

    if last >= support:
        near_sup = _pct_gap_below(last, support)
        support_def = 1.0 - _clamp01(near_sup / 0.02)
        support_def = max(support_def, 0.5)
    else:
        support_def = 0.2

    if last <= resistance:
        near_res = _pct_gap_above(last, resistance)
        res_clear = 1.0 - _clamp01(near_res / 0.02)
    else:
        res_clear = 0.9

    rvol_chip = _clamp01(0.5 + (rvol - 1.0))
    rs_chip = _clamp01(0.5 + rs_strength / 0.30)
    vwap_chip = _clamp01(0.5 + (vwap_diff / 0.04))

    return {
        "donchian": _to_int01(donchian_pos),
        "trend_dma": _to_int01(trend_dma),
        "support_def": _to_int01(support_def),
        "res_clear": _to_int01(res_clear),
        "rvol": _to_int01(rvol_chip),
        "rs": _to_int01(rs_chip),
        "vwap": _to_int01(vwap_chip),
    }


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
