"""Microchip extraction utilities for different timeframes."""

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


def _micro_from_features(
    features: dict[str, Any],
    *,
    near_pct: float,
    dma_scale: float,
) -> dict[str, int]:
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
    trend_dma = _clamp01(0.5 + rel_dma / dma_scale)

    if last >= support:
        near_support = _pct_gap_below(last, support)
        support_def = 1.0 - _clamp01(near_support / near_pct)
        support_def = max(support_def, 0.5)
    else:
        support_def = 0.2

    if last <= resistance:
        near_resistance = _pct_gap_above(last, resistance)
        res_clear = 1.0 - _clamp01(near_resistance / near_pct)
    else:
        res_clear = 0.9

    rvol_chip = _clamp01(0.5 + (rvol - 1.0) / 0.40)
    rs_chip = _clamp01(0.5 + rs_strength / 0.30)
    vwap_chip = _clamp01(0.5 + vwap_diff / 0.04)

    return {
        "donchian": _to_int01(donchian_pos),
        "trend_dma": _to_int01(trend_dma),
        "support_def": _to_int01(support_def),
        "res_clear": _to_int01(res_clear),
        "rvol": _to_int01(rvol_chip),
        "rs": _to_int01(rs_chip),
        "vwap": _to_int01(vwap_chip),
    }


def compute_microchips_m15(features: dict[str, Any]) -> dict[str, int]:
    return _micro_from_features(features, near_pct=0.02, dma_scale=0.10)


def compute_microchips_h60(features: dict[str, Any]) -> dict[str, int]:
    return _micro_from_features(features, near_pct=0.015, dma_scale=0.07)


def compute_microchips_daily(features: dict[str, Any]) -> dict[str, int]:
    return _micro_from_features(features, near_pct=0.01, dma_scale=0.05)
