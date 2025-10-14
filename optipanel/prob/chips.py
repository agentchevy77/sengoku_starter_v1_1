"""Probability chips engine derived from timeframe feature bundles."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

_CHIP_KEYS = (
    "breakout_up",
    "breakdown_down",
    "bounce_up",
    "rejection_down",
    "trend_long",
    "trend_short",
    "fakeout",
)


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _scale(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.5
    return _clamp01((value - lower) / (upper - lower))


def _safe_float(mapping: Mapping[str, Any], key: str, default: float) -> float:
    value = mapping.get(key, default)
    try:
        val = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(val) or math.isinf(val):
        return float(default)
    return val


def _compute_metrics(bundle: Mapping[str, Any]) -> dict[str, float]:
    last = _safe_float(bundle, "last", 0.0)
    dma = _safe_float(bundle, "dma20", last)
    support = _safe_float(bundle, "support", last)
    resistance = _safe_float(bundle, "resistance", last)
    rvol = _safe_float(bundle, "rvol", 1.0)
    rs = _safe_float(bundle, "rs_strength", 0.0)
    donchian = _clamp01(_safe_float(bundle, "donchian_pos", 0.5))
    obv = _safe_float(bundle, "obv_slope", 0.0)
    ad = _safe_float(bundle, "chaikin_ad", 0.0)
    clv_val = _safe_float(bundle, "clv", 0.0)
    avwap = _safe_float(bundle, "avwap_diff", 0.0)
    vwap_diff = _safe_float(bundle, "vwap_diff", 0.0)
    vwap_conf = _clamp01(_safe_float(bundle, "vwap_confluence", 0.0))

    magnitude = max(abs(last), 1.0)
    dma_pos = _scale(last - dma, -0.02 * magnitude, 0.02 * magnitude)
    dma_neg = 1.0 - dma_pos

    above_resistance = _scale(last - resistance, -0.005 * magnitude, 0.03 * magnitude)
    below_support = _scale(support - last, -0.005 * magnitude, 0.03 * magnitude)

    near_support = 1.0 - _scale(max(last - support, 0.0), 0.0, 0.02 * magnitude)
    near_resistance = 1.0 - _scale(max(resistance - last, 0.0), 0.0, 0.02 * magnitude)

    rvol_up = _scale(rvol, 0.9, 1.6)
    rvol_down = _scale(rvol, 0.7, 1.0)

    rs_pos = _scale(rs, -0.25, 0.25)
    rs_neg = 1.0 - rs_pos

    momentum_pos = (_scale(obv, -0.7, 0.7) + _scale(ad, -0.7, 0.7)) * 0.5
    momentum_neg = 1.0 - momentum_pos

    clv_pos = _scale(clv_val, -0.8, 0.8)
    clv_neg = 1.0 - clv_pos

    avwap_pos = _scale(avwap, -0.03, 0.03)
    avwap_neg = 1.0 - avwap_pos

    vwap_pos = _scale(vwap_diff, -0.03, 0.04)
    vwap_neg = 1.0 - vwap_pos

    momentum_divergence = abs(donchian - momentum_pos)
    fakeout_signal = _clamp01(0.6 * momentum_divergence + 0.2 * abs(donchian - rs_pos) + 0.2 * (1.0 - vwap_conf))

    breakout_up = (donchian + above_resistance + rvol_up + rs_pos + vwap_pos) / 5.0
    breakdown_down = ((1.0 - donchian) + below_support + rvol_down + rs_neg + vwap_neg) / 5.0
    bounce_up = (near_support + clv_pos + momentum_pos + rvol_up + vwap_pos) / 5.0
    rejection_down = (near_resistance + clv_neg + momentum_neg + rvol_down + vwap_neg) / 5.0
    trend_long = (dma_pos + rs_pos + momentum_pos + avwap_pos + vwap_pos) / 5.0
    trend_short = (dma_neg + rs_neg + momentum_neg + avwap_neg + vwap_neg) / 5.0

    return {
        "breakout_up": breakout_up,
        "breakdown_down": breakdown_down,
        "bounce_up": bounce_up,
        "rejection_down": rejection_down,
        "trend_long": trend_long,
        "trend_short": trend_short,
        "fakeout": fakeout_signal,
    }


def _to_ints(data: Mapping[str, float]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key in _CHIP_KEYS:
        value = _clamp01(float(data.get(key, 0.0)))
        out[key] = int(round(value * 100))
    return out


def compute_prob_chips(bundles_by_tf: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, int]]:
    if not bundles_by_tf:
        return {}

    chips: dict[str, dict[str, int]] = {}
    ordered_tfs = sorted(bundles_by_tf.keys())
    for tf in ordered_tfs:
        bundle = bundles_by_tf.get(tf) or {}
        metrics = _compute_metrics(bundle)
        chips[tf] = _to_ints(metrics)

    if chips:
        summary: dict[str, int] = {}
        count = len(chips)
        for key in _CHIP_KEYS:
            total = sum(chips[tf][key] for tf in chips)
            summary[key] = int(round(total / count))
        chips["summary"] = summary

    return chips
