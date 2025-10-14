"""Specification helpers for probability chips."""

from __future__ import annotations

import math
from typing import Any

REQUIRED_KEYS = (
    "last",
    "dma20",
    "support",
    "resistance",
    "rvol",
    "rs_strength",
    "vwap_diff",
)

# Optional extended fields used to bias probabilities
DEFAULTS: dict[str, float] = {
    "last": 0.0,
    "dma20": 0.0,
    "support": 0.0,
    "resistance": 0.0,
    "rvol": 1.0,
    "rs_strength": 0.0,
    "vwap_diff": 0.0,
    "donchian_pos": 0.5,
    "avwap_diff": 0.0,
    "obv_slope": 0.0,
    "chaikin_ad": 0.0,
    "clv": 0.0,
    "vwap_confluence": 0.0,
}

VALID_TIMEFRAMES = {"15m", "60m", "1d"}


def _safe_float(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        value = float(x)
    except (TypeError, ValueError):
        return default
    if math.isnan(value) or math.isinf(value):
        return default
    return value


def coerce_features(d: dict[str, Any]) -> dict[str, float]:
    """Coerce/cast all known fields to floats with defaults; ignore extras."""

    out: dict[str, float] = {}
    for key, default in DEFAULTS.items():
        val = _safe_float(d.get(key), default)
        out[key] = val
    return out
