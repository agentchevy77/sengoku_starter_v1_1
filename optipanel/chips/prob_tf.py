"""Canonical probability chips per timeframe."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from optipanel.prob.chips import compute_prob_chips

_FEATURE_KEYS = {
    "last",
    "dma20",
    "support",
    "resistance",
    "rvol",
    "rs_strength",
    "vwap_diff",
    "donchian_pos",
    "avwap_diff",
    "obv_slope",
    "chaikin_ad",
    "clv",
    "vwap_confluence",
}


def _select_features(src: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge allowed feature keys from source over fallback."""
    merged: dict[str, Any] = {}
    if isinstance(fallback, Mapping):
        for key in _FEATURE_KEYS:
            if key in fallback:
                merged[key] = fallback[key]
    if isinstance(src, Mapping):
        for key in _FEATURE_KEYS:
            if key in src:
                merged[key] = src[key]
    return merged


def _prob_single(tf: str, bundle: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None) -> dict[str, int]:
    features = _select_features(bundle, fallback)
    chips = compute_prob_chips({tf: features})
    view = chips.get(tf, {})
    return {name: int(round(float(value))) for name, value in view.items()}


def compute_probchips_m15(
    bundle_or_features: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None = None
) -> dict[str, int]:
    """Compute canonical probability chips for 15m data."""
    return _prob_single("15m", bundle_or_features, fallback)


def compute_probchips_h60(
    bundle_or_features: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None = None
) -> dict[str, int]:
    """Compute canonical probability chips for 60m data."""
    return _prob_single("60m", bundle_or_features, fallback)


def compute_probchips_daily(
    bundle_or_features: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None = None
) -> dict[str, int]:
    """Compute canonical probability chips for daily data."""
    return _prob_single("1d", bundle_or_features, fallback)
