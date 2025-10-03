from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from optipanel.battlefield.engine import compute_units
from optipanel.chips.aggregate import compute_sustainment, summarize_chips
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

    Bug #32 FIX: Updated advice logic to consult exhaustion and sustainability metrics
    before recommending aggressive positions, preventing dangerous trades on overextended
    or unreliable signals.

    Bug #34 FIX: All score-related fields now use consistent int type (0-100 range).
    Removed float values from sustainment to eliminate type ambiguity for API consumers.

    Returns:
      {
        "symbol": str,
        "units": dict[str, dict[str, int]],        # from compute_units(features)
        "setups": dict[str, int],                  # from compute_setups(features)
        "score": int,                              # 0..100 composite
        "advice": "attack" | "defend" | "standby",
        "sustainment": dict[str, int],             # sustainability and fakeout_risk scores (both int)
        "prob_chips": dict[str, dict[str, int]],   # probability chips by timeframe
        "prob_summary": dict[str, dict[str, int]], # summarized chip scores
        "battlefield_bundle": dict[str, float],    # raw market features (not scores)
        "features": dict[str, Any],                # original input features
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

    prob_chips_input = tf_bundles or {"1d": primary_bundle or fallback_bundle}
    prob_chips = compute_prob_chips(prob_chips_input)

    # Bug #32 FIX: Calculate sustainability to assess move reliability
    sustainment = compute_sustainment(prob_chips)

    # Bug #32 FIX: Multi-factor advice logic with safety checks
    # Extract risk metrics
    exhaustion = setups.get("exhaustion", 50)
    sustainability = sustainment.get("sustainability", 50)
    fakeout_risk = sustainment.get("fakeout_risk", 50)

    # Configurable thresholds for risk assessment
    EXHAUSTION_VETO = 70  # Too overextended/climactic
    SUSTAINABILITY_MIN = 40  # Move must be reliable
    FAKEOUT_RISK_MAX = 70  # Likely false signal

    # Multi-factor decision logic
    if score >= 65:
        # Strong bullish signal - apply safety checks
        if exhaustion < EXHAUSTION_VETO and sustainability >= SUSTAINABILITY_MIN and fakeout_risk < FAKEOUT_RISK_MAX:
            advice = "attack"
        else:
            # Signal strong but risk too high - wait
            advice = "standby"
    elif score <= 35:
        # Strong bearish signal - apply safety checks
        if exhaustion < EXHAUSTION_VETO and sustainability >= SUSTAINABILITY_MIN and fakeout_risk < FAKEOUT_RISK_MAX:
            advice = "defend"
        else:
            # Signal strong but risk too high - wait
            advice = "standby"
    else:
        advice = "standby"

    snapshot = {
        "symbol": symbol,
        "units": units,
        "setups": setups,
        "score": score,
        "advice": advice,
        "sustainment": sustainment,
        "battlefield_bundle": dict(primary_bundle) if primary_bundle else dict(fallback_bundle),
        "prob_chips": prob_chips,
    }
    snapshot["prob_summary"] = summarize_chips(prob_chips)
    snapshot["features"] = dict(features)
    return snapshot
