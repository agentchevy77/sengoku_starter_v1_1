from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SetupConfig:
    """
    Configuration for the Battlefield Scoring Engine.

    These parameters define the quantitative model used to score various
    trading setups. Each threshold and multiplier has been tuned and should
    be treated as part of the model specification.

    All scores range from 0-100. Gap thresholds are percentages (0.01 = 1%).

    Changing these values alters the model's behavior and may invalidate
    backtests and historical analysis.
    """

    # === BREAKOUT UP (price breaking above resistance) ===
    breakout_up_gap_max: float = 0.01  # Max gap for "near" classification (1%)
    breakout_up_base_broken: float = 85.0  # Base score when already broken (gap <= 0)
    breakout_up_base_near: float = 60.0  # Base score when near resistance
    breakout_up_base_far: float = 30.0  # Base score when far from resistance
    breakout_up_rvol_thresh: float = 1.2  # Relative volume threshold for bonus
    breakout_up_rvol_bonus: float = 10.0  # Bonus for high rvol
    breakout_up_rs_thresh: float = 0.1  # Relative strength threshold
    breakout_up_rs_bonus: float = 10.0  # Bonus for strong RS
    breakout_up_dma_bonus: float = 5.0  # Bonus for price above 20 DMA

    # === BREAKDOWN DOWN (price breaking below support) ===
    breakdown_down_gap_max: float = 0.01  # Max gap for "near" classification
    breakdown_down_base_broken: float = 85.0  # Base score when already broken
    breakdown_down_base_near: float = 60.0  # Base score when near support
    breakdown_down_base_far: float = 30.0  # Base score when far from support
    breakdown_down_rvol_thresh: float = 1.2  # Relative volume threshold
    breakdown_down_rvol_bonus: float = 10.0  # Bonus for high rvol
    breakdown_down_rs_thresh: float = -0.1  # Relative strength threshold (negative)
    breakdown_down_rs_bonus: float = 10.0  # Bonus for weak RS
    breakdown_down_dma_bonus: float = 5.0  # Bonus for price below 20 DMA

    # === BOUNCE UP (defending support level) ===
    bounce_up_gap_max: float = 0.01  # Max gap for "near" classification
    bounce_up_base_near_max: float = 70.0  # Max base score when very near support
    bounce_up_base_near_min: float = 50.0  # Min base score when near support
    bounce_up_base_far: float = 35.0  # Base score when away from support
    bounce_up_base_broken: float = 20.0  # Score when support is broken
    bounce_up_dma_bonus: float = 10.0  # Bonus for price above 20 DMA
    bounce_up_rs_bonus: float = 5.0  # Bonus for positive RS
    bounce_up_rvol_thresh: float = 1.0  # Relative volume threshold
    bounce_up_rvol_bonus: float = 5.0  # Bonus for elevated volume

    # === REJECTION DOWN (failing at resistance) ===
    rejection_down_gap_max: float = 0.01  # Max gap for "near" classification
    rejection_down_base_near_max: float = 60.0  # Max base score when very near resistance
    rejection_down_base_near_min: float = 45.0  # Min base score when near resistance
    rejection_down_base_far: float = 30.0  # Base score when away from resistance
    rejection_down_base_broken: float = 25.0  # Score when resistance is broken
    rejection_down_dma_malus: float = 10.0  # Penalty for price below 20 DMA
    rejection_down_rs_malus: float = 10.0  # Penalty for weak RS
    rejection_down_rvol_thresh: float = 1.0  # Relative volume threshold
    rejection_down_rvol_malus: float = 5.0  # Penalty for high volume with bearish confirmation

    # === TREND CONTINUATION (long and short) ===
    trend_base_strong: float = 55.0  # Base score when aligned with trend
    trend_base_weak: float = 25.0  # Base score when against trend
    trend_vwap_bonus: float = 10.0  # Bonus for price aligned with VWAP
    trend_rvol_thresh: float = 1.2  # Relative volume threshold
    trend_rvol_bonus: float = 10.0  # Bonus for high volume
    trend_long_rs_strong: float = 0.1  # RS threshold for strong trend_long
    trend_long_rs_weak: float = 0.0  # RS threshold for weak trend_long
    trend_short_rs_strong: float = -0.1  # RS threshold for strong trend_short
    trend_short_rs_weak: float = 0.0  # RS threshold for weak trend_short
    trend_rs_strong_bonus: float = 15.0  # Bonus for strong RS alignment
    trend_rs_weak_bonus: float = 5.0  # Bonus for weak RS alignment

    # === EXHAUSTION (overextension risk) ===
    exhaustion_base: float = 30.0  # Base score (no extension)
    exhaustion_ext_min: float = 0.05  # Minimum extension to trigger (5%)
    exhaustion_ext_max: float = 0.10  # Extension for max score (10%)
    exhaustion_ext_base: float = 60.0  # Base score when extension detected
    exhaustion_ext_range: float = 20.0  # Additional range for scaling (60->80)
    exhaustion_rvol_thresh: float = 1.5  # Relative volume threshold
    exhaustion_rvol_bonus: float = 10.0  # Bonus for extreme volume


def _as_float(value: object, default: float = 0.0) -> float:
    """Safely convert value to float, returning default on failure."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Failed to convert value to float: %r", value)
        return default


def _clamp_int(x: float) -> int:
    x = int(round(x))
    return 0 if x < 0 else 100 if x > 100 else x


def _pct_gap_above(last: float, level: float) -> float:
    if last <= 0:
        return 1e9
    return (level - last) / last


def _pct_gap_below(last: float, level: float) -> float:
    if last <= 0:
        return 1e9
    return (last - level) / last


def compute_setups(features: dict[str, Any], config: SetupConfig | None = None) -> dict[str, int]:
    """
    Deterministic 0..100 scores for:
    breakout_up, breakdown_down, bounce_up, rejection_down, trend_long, trend_short, exhaustion.
    Uses: last, dma20, support, resistance, rvol, rs_strength, vwap_diff (optional; default 0.0).

    Missing or invalid values fall back to sensible defaults instead of raising exceptions.

    Args:
        features: Dictionary containing market data features
        config: Optional SetupConfig for custom thresholds. If None, uses default values.

    Returns:
        Dictionary mapping setup names to scores (0-100)
    """
    if config is None:
        config = SetupConfig()

    # Required fields - use 0.0 as fallback (will produce neutral scores)
    last = _as_float(features.get("last"), default=0.0)
    dma20 = _as_float(features.get("dma20"), default=0.0)
    support = _as_float(features.get("support"), default=0.0)
    resistance = _as_float(features.get("resistance"), default=0.0)

    # Optional fields with documented defaults
    rvol = _as_float(features.get("rvol"), default=1.0)
    rs = _as_float(features.get("rs_strength"), default=0.0)
    vwap_diff = _as_float(features.get("vwap_diff"), default=0.0)

    out: dict[str, int] = {}

    # Breakout up
    gap = _pct_gap_above(last, resistance)
    if gap <= 0:
        base = config.breakout_up_base_broken
    elif gap <= config.breakout_up_gap_max:
        # Linear interpolation: near -> broken as gap decreases
        base = config.breakout_up_base_near + (config.breakout_up_base_broken - config.breakout_up_base_near) * (
            1 - gap / config.breakout_up_gap_max
        )
    else:
        base = config.breakout_up_base_far

    bonus = (
        (config.breakout_up_rvol_bonus if rvol >= config.breakout_up_rvol_thresh else 0)
        + (config.breakout_up_rs_bonus if rs >= config.breakout_up_rs_thresh else 0)
        + (config.breakout_up_dma_bonus if last >= dma20 else 0)
    )
    out["breakout_up"] = _clamp_int(base + float(bonus))

    # Breakdown down
    near_sup = _pct_gap_below(last, support)  # >=0 when above support
    if last < support:
        base = config.breakdown_down_base_broken
    elif near_sup <= config.breakdown_down_gap_max:
        # Linear interpolation: near -> broken as gap decreases
        base = config.breakdown_down_base_near + (
            config.breakdown_down_base_broken - config.breakdown_down_base_near
        ) * (1 - max(0.0, near_sup) / config.breakdown_down_gap_max)
    else:
        base = config.breakdown_down_base_far

    bonus = (
        (config.breakdown_down_rvol_bonus if rvol >= config.breakdown_down_rvol_thresh else 0)
        + (config.breakdown_down_rs_bonus if rs <= config.breakdown_down_rs_thresh else 0)
        + (config.breakdown_down_dma_bonus if last < dma20 else 0)
    )
    out["breakdown_down"] = _clamp_int(base + float(bonus))

    # Bounce up (defend support)
    if last >= support:
        near = max(0.0, near_sup)
        if near <= config.bounce_up_gap_max:
            # Linear interpolation: min -> max as gap decreases
            base = config.bounce_up_base_near_min + (
                config.bounce_up_base_near_max - config.bounce_up_base_near_min
            ) * (1 - near / config.bounce_up_gap_max)
        else:
            base = config.bounce_up_base_far

        bonus = (
            (config.bounce_up_dma_bonus if last >= dma20 else 0)
            + (config.bounce_up_rs_bonus if rs >= 0.0 else 0)
            + (config.bounce_up_rvol_bonus if rvol >= config.bounce_up_rvol_thresh else 0)
        )
        out["bounce_up"] = _clamp_int(base + float(bonus))
    else:
        out["bounce_up"] = _clamp_int(config.bounce_up_base_broken)

    # Rejection down (fail at resistance)
    if last <= resistance:
        near = max(0.0, _pct_gap_above(last, resistance))
        if near <= config.rejection_down_gap_max:
            # Linear interpolation: min -> max as gap decreases
            base = config.rejection_down_base_near_min + (
                config.rejection_down_base_near_max - config.rejection_down_base_near_min
            ) * (1 - near / config.rejection_down_gap_max)
        else:
            base = config.rejection_down_base_far

        malus = 0
        if last < dma20:
            malus += config.rejection_down_dma_malus
        if rs <= 0.0:
            malus += config.rejection_down_rs_malus
        # Only count RVOL against the bull case if bearish confirmation exists
        if (last < dma20 or rs <= 0.0) and rvol >= config.rejection_down_rvol_thresh:
            malus += config.rejection_down_rvol_malus
        out["rejection_down"] = _clamp_int(base + float(malus))
    else:
        out["rejection_down"] = _clamp_int(config.rejection_down_base_broken)

    # Trend continuation long/short
    score_long = config.trend_base_strong if last >= dma20 else config.trend_base_weak
    score_long += config.trend_vwap_bonus if vwap_diff >= 0 else 0
    score_long += config.trend_rvol_bonus if rvol >= config.trend_rvol_thresh else 0
    if rs >= config.trend_long_rs_strong:
        score_long += config.trend_rs_strong_bonus
    elif rs >= config.trend_long_rs_weak:
        score_long += config.trend_rs_weak_bonus
    out["trend_long"] = _clamp_int(score_long)

    score_short = config.trend_base_strong if last < dma20 else config.trend_base_weak
    score_short += config.trend_vwap_bonus if vwap_diff <= 0 else 0
    score_short += config.trend_rvol_bonus if rvol >= config.trend_rvol_thresh else 0
    if rs <= config.trend_short_rs_strong:
        score_short += config.trend_rs_strong_bonus
    elif rs <= config.trend_short_rs_weak:
        score_short += config.trend_rs_weak_bonus
    out["trend_short"] = _clamp_int(score_short)

    # Exhaustion risk (extension from dma20 + high RVOL)
    ext = abs(last - dma20) / last if last else 0.0
    exh = config.exhaustion_base
    if ext >= config.exhaustion_ext_min:
        # Linear scaling from ext_min to ext_max -> adds ext_range on top of ext_base
        # Original: 60 + 20 * min(1.0, (ext - 0.05) / 0.05)
        # This gives: 60->80 as ext goes from 5% to 10%
        exh = config.exhaustion_ext_base + config.exhaustion_ext_range * min(
            1.0, (ext - config.exhaustion_ext_min) / (config.exhaustion_ext_max - config.exhaustion_ext_min)
        )
    if rvol >= config.exhaustion_rvol_thresh:
        exh += config.exhaustion_rvol_bonus
    out["exhaustion"] = _clamp_int(exh)

    return out
