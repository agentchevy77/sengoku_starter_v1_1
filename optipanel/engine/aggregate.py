from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from optipanel.battlefield.engine import compute_units
from optipanel.chips.aggregate import summarize_chips
from optipanel.prob.chips import compute_prob_chips
from optipanel.setups.engine import compute_setups


def _clamp_int(x: float) -> int:
    x = int(round(x))
    return 0 if x < 0 else 100 if x > 100 else x


def _bundle_from_features(features: Mapping[str, Any]) -> dict[str, float]:
    bundle: dict[str, float] = {}
    for key, value in features.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(val) or math.isinf(val):
            continue
        bundle[key] = val
    return bundle


def _extract_timeframe_bundles(features: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    bundles: dict[str, dict[str, float]] = {}
    tf_map = features.get("bundles") if isinstance(features, Mapping) else None
    if isinstance(tf_map, Mapping):
        for tf, data in tf_map.items():
            if not isinstance(data, Mapping):
                continue
            bundle = _bundle_from_features(data)
            if bundle:
                bundles[str(tf)] = bundle
    return bundles


def _select_primary_bundle(
    bundles: Mapping[str, dict[str, float]],
    fallback: dict[str, float],
) -> dict[str, float]:
    for tf in ("1d", "60m", "15m"):
        data = bundles.get(tf)
        if data:
            return data
    for data in bundles.values():
        if data:
            return data
    return fallback


def _ensure_required_fields(bundle: dict[str, float], fallback: Mapping[str, float], raw: Mapping[str, Any]) -> None:
    required = ("last", "dma20", "support", "resistance", "rvol", "rs_strength", "vwap_diff")
    for key in required:
        if key in bundle:
            continue
        if key in fallback:
            bundle[key] = fallback[key]
            continue
        value = raw.get(key)
        if isinstance(value, int | float) and not (math.isnan(value) or math.isinf(value)):
            bundle[key] = float(value)


def build_symbol_snapshot(symbol: str, features: dict[str, Any]) -> dict[str, Any]:
    """
    Pure aggregator that combines battlefield 'units' and setup scores into a single view.

    Returns:
      {
        "symbol": str,
        "units": dict,   # from compute_units(features)
        "setups": dict,  # from compute_setups(features)
        "score": int,    # 0..100 composite
        "advice": "attack" | "defend" | "standby",
      }
    """
    tf_bundles = _extract_timeframe_bundles(features)
    fallback_bundle = _bundle_from_features(features)
    primary_bundle = _select_primary_bundle(tf_bundles, fallback_bundle)
    primary_bundle = dict(primary_bundle) if primary_bundle else {}
    _ensure_required_fields(primary_bundle, fallback_bundle, features)

    units = compute_units(primary_bundle or features)
    setups = compute_setups(primary_bundle or features)

    # Simple, deterministic composite:
    # bias = (trend_long - trend_short) + (breakout_up - breakdown_down)
    trend_bias = setups.get("trend_long", 0) - setups.get("trend_short", 0)
    breakout_bias = setups.get("breakout_up", 0) - setups.get("breakdown_down", 0)
    bias = trend_bias + breakout_bias

    score = _clamp_int(50 + 0.5 * bias)

    if score >= 65:
        advice = "attack"
    elif score <= 35:
        advice = "defend"
    else:
        advice = "standby"

    prob_chips_input = tf_bundles or {"1d": primary_bundle or fallback_bundle}
    prob_chips = compute_prob_chips(prob_chips_input)

    snapshot = {
        "symbol": symbol,
        "units": units,
        "setups": setups,
        "score": score,
        "advice": advice,
        "battlefield_bundle": dict(primary_bundle) if primary_bundle else dict(fallback_bundle),
        "prob_chips": prob_chips,
    }
    snapshot["prob_summary"] = summarize_chips(prob_chips)
    snapshot["features"] = dict(features)
    return snapshot
