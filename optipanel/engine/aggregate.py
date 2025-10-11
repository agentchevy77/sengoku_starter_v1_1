from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from optipanel.battlefield.engine import compute_units
from optipanel.chips.aggregate import compute_sustainment, summarize_chips
from optipanel.prob.chips import compute_prob_chips
from optipanel.setups.engine import SetupConfig, compute_setups
from optipanel.utils.decimal_types import D_ZERO, clamp_score, to_decimal


def _clamp_int(x: Decimal) -> int:
    """Clamp Decimal value to 0-100 integer range."""
    return clamp_score(x, lo=0, hi=100)


def _calculate_risk_penalty(
    exhaustion: Decimal,
    sustainability: Decimal,
    fakeout_risk: Decimal,
    config: SetupConfig,
) -> Decimal:
    """
    Calculate score penalty based on risk metrics.

    Bug #33 FIX: This function quantifies risk as a score reduction, ensuring that
    the final ranking reflects both opportunity (signal strength) AND risk (sustainability).

    Bug #39 FIX: Thresholds are now configurable via SetupConfig instead of hardcoded.

    Only penalizes when risk metrics exceed safe thresholds (configurable):
    - Exhaustion > advice_exhaustion_veto: Symbol is overextended/climactic
    - Sustainability < advice_sustainability_min: Move is unreliable
    - Fakeout Risk > advice_fakeout_risk_max: Signal likely to reverse

    Args:
        exhaustion: Overextension metric (0-100, higher = more exhausted)
        sustainability: Move reliability metric (0-100, higher = more reliable)
        fakeout_risk: False signal probability (0-100, higher = more risky)
        config: Setup configuration with risk thresholds

    Returns:
        Total penalty to subtract from base score (0-50 range)
    """
    # Penalty thresholds from config (Bug #39 fix - now configurable)
    exhaustion_threshold = Decimal(str(config.advice_exhaustion_veto))
    sustainability_threshold = Decimal(str(config.advice_sustainability_min))
    fakeout_threshold = Decimal(str(config.advice_fakeout_risk_max))

    # Penalty weight: each point of excess risk reduces score by 0.5 points
    penalty_weight = Decimal("0.5")

    # Calculate individual penalties (only when threshold exceeded)
    exhaustion_penalty = max(D_ZERO, exhaustion - exhaustion_threshold) * penalty_weight
    sustainability_penalty = max(D_ZERO, sustainability_threshold - sustainability) * penalty_weight
    fakeout_penalty = max(D_ZERO, fakeout_risk - fakeout_threshold) * penalty_weight

    # Total penalty (capped at 50 to ensure score can't go below 0)
    total_penalty = exhaustion_penalty + sustainability_penalty + fakeout_penalty
    return min(total_penalty, Decimal("50"))


def _bundle_from_features(features: Mapping[str, Any]) -> dict[str, Decimal]:
    """Convert features to Decimal bundle, filtering out invalid values."""
    bundle: dict[str, Decimal] = {}
    for key, value in features.items():
        try:
            val = to_decimal(value, default=None)
            if val is None or not val.is_finite():
                continue
            bundle[key] = val
        except (TypeError, ValueError):
            continue
    return bundle


def _extract_timeframe_bundles(features: Mapping[str, Any]) -> dict[str, dict[str, Decimal]]:
    """Extract timeframe bundles with Decimal precision."""
    bundles: dict[str, dict[str, Decimal]] = {}
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
    bundles: Mapping[str, dict[str, Decimal]],
    fallback: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Select primary bundle for analysis."""
    for tf in ("1d", "60m", "15m"):
        data = bundles.get(tf)
        if data:
            return data
    for data in bundles.values():
        if data:
            return data
    return fallback


def _ensure_required_fields(
    bundle: dict[str, Decimal], fallback: Mapping[str, Decimal], raw: Mapping[str, Any]
) -> None:
    """Ensure all required fields are present with Decimal precision."""
    required = ("last", "dma20", "support", "resistance", "rvol", "rs_strength", "vwap_diff")
    for key in required:
        if key in bundle:
            continue
        if key in fallback:
            bundle[key] = fallback[key]
            continue
        value = raw.get(key)
        if value is not None:
            decimal_val = to_decimal(value, default=None)
            if decimal_val is not None and decimal_val.is_finite():
                bundle[key] = decimal_val


def build_symbol_snapshot(
    symbol: str,
    features: dict[str, Any],
    config: SetupConfig | None = None,
) -> dict[str, Any]:
    """
    Pure aggregator that combines battlefield 'units' and setup scores into a single view.

    Bug #32 FIX: Updated advice logic to consult exhaustion and sustainability metrics
    before recommending aggressive positions, preventing dangerous trades on overextended
    or unreliable signals.

    Bug #33 FIX: Final score now incorporates risk metrics (exhaustion, sustainability,
    fakeout_risk) via a penalty system. This ensures symbols are ranked by both opportunity
    AND risk, preventing dangerous over-extended symbols from ranking higher than safer
    opportunities. Risk penalties only apply when thresholds are exceeded.

    Bug #34 FIX: All score-related fields now use consistent int type (0-100 range).
    Removed float values from sustainment to eliminate type ambiguity for API consumers.

    Bug #36 FIX: All financial calculations now use Decimal type for exact arithmetic,
    eliminating floating-point rounding errors that could compound in score calculations.

    Bug #39 FIX: Risk thresholds are now configurable via SetupConfig parameter instead
    of hardcoded constants. Allows testing different risk tolerance levels.

    Args:
        symbol: Trading symbol (e.g., "AAPL")
        features: Market data features dictionary
        config: Optional SetupConfig for custom thresholds. If None, uses defaults.

    Returns:
      {
        "symbol": str,
        "units": dict[str, dict[str, int]],        # from compute_units(features)
        "setups": dict[str, int],                  # from compute_setups(features)
        "score": int,                              # 0..100 risk-adjusted composite
        "advice": "attack" | "defend" | "standby",
        "sustainment": dict[str, int],             # sustainability and fakeout_risk scores (both int)
        "prob_chips": dict[str, dict[str, int]],   # probability chips by timeframe
        "prob_summary": dict[str, dict[str, int]], # summarized chip scores
        "battlefield_bundle": dict[str, float],    # raw market features (not scores)
        "features": dict[str, Any],                # original input features
      }
    """
    # Bug #39 FIX: Use provided config or create default
    if config is None:
        config = SetupConfig()
    tf_bundles = _extract_timeframe_bundles(features)
    fallback_bundle = _bundle_from_features(features)
    primary_bundle = _select_primary_bundle(tf_bundles, fallback_bundle)
    primary_bundle = dict(primary_bundle) if primary_bundle else {}
    _ensure_required_fields(primary_bundle, fallback_bundle, features)

    units = compute_units(primary_bundle or features)
    # Bug #39 FIX: Pass config to compute_setups for custom thresholds
    setups = compute_setups(primary_bundle or features, config=config)

    # Simple, deterministic composite using Decimal for precision:
    # bias = (trend_long - trend_short) + (breakout_up - breakdown_down)
    trend_long = to_decimal(setups.get("trend_long", 0))
    trend_short = to_decimal(setups.get("trend_short", 0))
    breakout_up = to_decimal(setups.get("breakout_up", 0))
    breakdown_down = to_decimal(setups.get("breakdown_down", 0))

    trend_bias = trend_long - trend_short
    breakout_bias = breakout_up - breakdown_down
    bias = trend_bias + breakout_bias

    # Calculate base signal score with Decimal precision
    base_signal_score = Decimal("50") + Decimal("0.5") * bias

    prob_chips_input = tf_bundles or {"1d": primary_bundle or fallback_bundle}
    prob_chips = compute_prob_chips(prob_chips_input)

    # Bug #32 FIX: Calculate sustainability to assess move reliability
    sustainment = compute_sustainment(prob_chips)

    # Bug #32 FIX: Multi-factor advice logic with safety checks
    # Extract risk metrics using Decimal for exact comparisons
    exhaustion = to_decimal(setups.get("exhaustion", 50))
    sustainability = to_decimal(sustainment.get("sustainability", 50))
    fakeout_risk = to_decimal(sustainment.get("fakeout_risk", 50))

    # Bug #33 FIX: Apply risk penalty to base score
    # This ensures final score reflects BOTH opportunity AND risk
    # Bug #39 FIX: Pass config to use configurable thresholds
    risk_penalty = _calculate_risk_penalty(exhaustion, sustainability, fakeout_risk, config)
    score = _clamp_int(base_signal_score - risk_penalty)

    # Bug #39 FIX: Use configurable thresholds from SetupConfig instead of hardcoded values
    exhaustion_veto = Decimal(str(config.advice_exhaustion_veto))
    sustainability_min = Decimal(str(config.advice_sustainability_min))
    fakeout_risk_max = Decimal(str(config.advice_fakeout_risk_max))

    # Multi-factor decision logic with Decimal precision
    if score >= 65:
        # Strong bullish signal - apply safety checks
        if exhaustion < exhaustion_veto and sustainability >= sustainability_min and fakeout_risk < fakeout_risk_max:
            advice = "attack"
        else:
            # Signal strong but risk too high - wait
            advice = "standby"
    elif score <= 35:
        # Strong bearish signal - apply safety checks
        if exhaustion < exhaustion_veto and sustainability >= sustainability_min and fakeout_risk < fakeout_risk_max:
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
