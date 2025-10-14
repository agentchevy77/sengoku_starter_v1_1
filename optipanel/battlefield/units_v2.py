"""Battlefield units mapping for the v1.1 feature bundle."""

from __future__ import annotations

from collections.abc import Mapping

_EPS = 1e-9


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _scale_to_unit(value: float, lower: float, upper: float) -> float:
    """Linearly map *value* into 0..1, guarding invalid bounds."""
    if upper <= lower:
        return 0.5
    return _clamp01((value - lower) / (upper - lower))


def _pair(score: float) -> dict[str, int]:
    score = _clamp01(score)
    bull = int(round(score * 100))
    return {"bull": bull, "bear": 100 - bull}


def _safe_get(bundle: Mapping[str, float], key: str, default: float) -> float:
    value = bundle.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _support_strength(last: float, support: float) -> float:
    if abs(last) <= _EPS:
        return 0.5
    gap_pct = (last - support) / max(abs(last), 1.0)
    return _clamp01(0.5 + gap_pct / 0.03)


def _resistance_strength(last: float, resistance: float) -> float:
    if abs(last) <= _EPS:
        return 0.5
    distance_pct = (resistance - last) / max(abs(last), 1.0)
    return _scale_to_unit(distance_pct, 0.0, 0.03)


def _rvol_strength(rvol: float) -> float:
    return _scale_to_unit(rvol, 0.7, 1.3)


def _rs_strength(rs: float) -> float:
    return _scale_to_unit(rs, -0.25, 0.25)


def _slope_strength(value: float, span: float = 0.6) -> float:
    return _scale_to_unit(value, -span, span)


def _clv_strength(clv_value: float) -> float:
    return _scale_to_unit(clv_value, -0.7, 0.7)


def _avwap_strength(diff: float) -> float:
    return _scale_to_unit(diff, -0.03, 0.03)


def compute_units_v2(bundle: Mapping[str, float] | None) -> dict[str, dict[str, int]]:
    """Translate a feature bundle into bull/bear battlefield intensities."""
    bundle = bundle or {}

    last = _safe_get(bundle, "last", 0.0)
    dma = _safe_get(bundle, "dma20", last)
    support = _safe_get(bundle, "support", last)
    resistance = _safe_get(bundle, "resistance", last)
    rvol = _safe_get(bundle, "rvol", 1.0)
    rs = _safe_get(bundle, "rs_strength", 0.0)
    donchian = _safe_get(bundle, "donchian_pos", 0.5)
    obv = _safe_get(bundle, "obv_slope", 0.0)
    ad = _safe_get(bundle, "chaikin_ad", 0.0)
    clv_val = _safe_get(bundle, "clv", 0.0)
    avwap = _safe_get(bundle, "avwap_diff", 0.0)

    dma_strength = _scale_to_unit(last - dma, -0.02 * max(abs(last), 1.0), 0.02 * max(abs(last), 1.0))
    support_strength = _support_strength(last, support)
    resistance_strength = _resistance_strength(last, resistance)
    rvol_strength = _rvol_strength(rvol)
    rs_strength = _rs_strength(rs)
    donchian_strength = _clamp01(donchian)
    obv_strength = _slope_strength(obv)
    ad_strength = _slope_strength(ad)
    clv_strength = _clv_strength(clv_val)
    avwap_strength = _avwap_strength(avwap)

    return {
        "dma20": _pair(dma_strength),
        "support": _pair(support_strength),
        "resistance": _pair(resistance_strength),
        "rvol": _pair(rvol_strength),
        "rs": _pair(rs_strength),
        "donchian": _pair(donchian_strength),
        "obv": _pair(obv_strength),
        "ad": _pair(ad_strength),
        "clv": _pair(clv_strength),
        "avwap": _pair(avwap_strength),
    }
