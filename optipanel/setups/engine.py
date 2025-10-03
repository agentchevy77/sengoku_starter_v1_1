from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from optipanel.utils.decimal_types import (
    D_ONE,
    D_ZERO,
    clamp_score,
    pct_gap_above,
    pct_gap_below,
    to_decimal,
)

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


def _as_decimal(value: object, default: Decimal = D_ZERO) -> Decimal:
    """Safely convert value to Decimal, returning default on failure.

    Uses Decimal for precise financial calculations.
    """
    result = to_decimal(value, default=default)
    if result is None or not result.is_finite():
        logger.warning("Failed to convert value to Decimal: %r", value)
        return default
    return result


def compute_setups(features: dict[str, Any], config: SetupConfig | None = None) -> dict[str, int]:
    """
    Deterministic 0..100 scores for:
    breakout_up, breakdown_down, bounce_up, rejection_down, trend_long, trend_short, exhaustion.
    Uses: last, dma20, support, resistance, rvol, rs_strength, vwap_diff (optional; default 0.0).

    Missing or invalid values fall back to sensible defaults instead of raising exceptions.

    Uses Decimal arithmetic for precise percentage gap calculations to avoid floating-point errors.

    Args:
        features: Dictionary containing market data features
        config: Optional SetupConfig for custom thresholds. If None, uses default values.

    Returns:
        Dictionary mapping setup names to scores (0-100)
    """
    if config is None:
        config = SetupConfig()

    # Required fields - use 0.0 as fallback (will produce neutral scores)
    # Convert to Decimal for precise calculations
    last = _as_decimal(features.get("last"), default=D_ZERO)
    dma20 = _as_decimal(features.get("dma20"), default=D_ZERO)
    support = _as_decimal(features.get("support"), default=D_ZERO)
    resistance = _as_decimal(features.get("resistance"), default=D_ZERO)

    # Optional fields with documented defaults
    rvol = _as_decimal(features.get("rvol"), default=D_ONE)
    rs = _as_decimal(features.get("rs_strength"), default=D_ZERO)
    vwap_diff = _as_decimal(features.get("vwap_diff"), default=D_ZERO)

    out: dict[str, int] = {}

    # Breakout up - using Decimal for precise gap calculations
    gap = pct_gap_above(last, resistance)
    gap_max_d = Decimal(str(config.breakout_up_gap_max))

    if gap <= D_ZERO:
        base = Decimal(str(config.breakout_up_base_broken))
    elif gap <= gap_max_d:
        # Linear interpolation: near -> broken as gap decreases
        base_near = Decimal(str(config.breakout_up_base_near))
        base_broken = Decimal(str(config.breakout_up_base_broken))
        base = base_near + (base_broken - base_near) * (D_ONE - gap / gap_max_d)
    else:
        base = Decimal(str(config.breakout_up_base_far))

    bonus = D_ZERO
    if rvol >= Decimal(str(config.breakout_up_rvol_thresh)):
        bonus += Decimal(str(config.breakout_up_rvol_bonus))
    if rs >= Decimal(str(config.breakout_up_rs_thresh)):
        bonus += Decimal(str(config.breakout_up_rs_bonus))
    if last >= dma20:
        bonus += Decimal(str(config.breakout_up_dma_bonus))

    out["breakout_up"] = clamp_score(base + bonus)

    # Breakdown down - using Decimal for precise gap calculations
    near_sup = pct_gap_below(last, support)  # >=0 when above support
    gap_max_bd = Decimal(str(config.breakdown_down_gap_max))

    if last < support:
        base = Decimal(str(config.breakdown_down_base_broken))
    elif near_sup <= gap_max_bd:
        # Linear interpolation: near -> broken as gap decreases
        base_near = Decimal(str(config.breakdown_down_base_near))
        base_broken = Decimal(str(config.breakdown_down_base_broken))
        near_sup_clamped = max(D_ZERO, near_sup)
        base = base_near + (base_broken - base_near) * (D_ONE - near_sup_clamped / gap_max_bd)
    else:
        base = Decimal(str(config.breakdown_down_base_far))

    bonus = D_ZERO
    if rvol >= Decimal(str(config.breakdown_down_rvol_thresh)):
        bonus += Decimal(str(config.breakdown_down_rvol_bonus))
    if rs <= Decimal(str(config.breakdown_down_rs_thresh)):
        bonus += Decimal(str(config.breakdown_down_rs_bonus))
    if last < dma20:
        bonus += Decimal(str(config.breakdown_down_dma_bonus))

    out["breakdown_down"] = clamp_score(base + bonus)

    # Bounce up (defend support) - using Decimal for precise gap calculations
    if last >= support:
        near = max(D_ZERO, near_sup)
        gap_max_bu = Decimal(str(config.bounce_up_gap_max))

        if near <= gap_max_bu:
            # Linear interpolation: min -> max as gap decreases
            base_min = Decimal(str(config.bounce_up_base_near_min))
            base_max = Decimal(str(config.bounce_up_base_near_max))
            base = base_min + (base_max - base_min) * (D_ONE - near / gap_max_bu)
        else:
            base = Decimal(str(config.bounce_up_base_far))

        bonus = D_ZERO
        if last >= dma20:
            bonus += Decimal(str(config.bounce_up_dma_bonus))
        if rs >= D_ZERO:
            bonus += Decimal(str(config.bounce_up_rs_bonus))
        if rvol >= Decimal(str(config.bounce_up_rvol_thresh)):
            bonus += Decimal(str(config.bounce_up_rvol_bonus))

        out["bounce_up"] = clamp_score(base + bonus)
    else:
        out["bounce_up"] = clamp_score(Decimal(str(config.bounce_up_base_broken)))

    # Rejection down (fail at resistance) - using Decimal for precise gap calculations
    if last <= resistance:
        near = max(D_ZERO, pct_gap_above(last, resistance))
        gap_max_rd = Decimal(str(config.rejection_down_gap_max))

        if near <= gap_max_rd:
            # Linear interpolation: min -> max as gap decreases
            base_min = Decimal(str(config.rejection_down_base_near_min))
            base_max = Decimal(str(config.rejection_down_base_near_max))
            base = base_min + (base_max - base_min) * (D_ONE - near / gap_max_rd)
        else:
            base = Decimal(str(config.rejection_down_base_far))

        malus = D_ZERO
        if last < dma20:
            malus += Decimal(str(config.rejection_down_dma_malus))
        if rs <= D_ZERO:
            malus += Decimal(str(config.rejection_down_rs_malus))
        # Only count RVOL against the bull case if bearish confirmation exists
        if (last < dma20 or rs <= D_ZERO) and rvol >= Decimal(str(config.rejection_down_rvol_thresh)):
            malus += Decimal(str(config.rejection_down_rvol_malus))

        out["rejection_down"] = clamp_score(base + malus)
    else:
        out["rejection_down"] = clamp_score(Decimal(str(config.rejection_down_base_broken)))

    # Trend continuation long/short - using Decimal for precise calculations
    score_long = Decimal(str(config.trend_base_strong if last >= dma20 else config.trend_base_weak))
    if vwap_diff >= D_ZERO:
        score_long += Decimal(str(config.trend_vwap_bonus))
    if rvol >= Decimal(str(config.trend_rvol_thresh)):
        score_long += Decimal(str(config.trend_rvol_bonus))
    if rs >= Decimal(str(config.trend_long_rs_strong)):
        score_long += Decimal(str(config.trend_rs_strong_bonus))
    elif rs >= Decimal(str(config.trend_long_rs_weak)):
        score_long += Decimal(str(config.trend_rs_weak_bonus))
    out["trend_long"] = clamp_score(score_long)

    score_short = Decimal(str(config.trend_base_strong if last < dma20 else config.trend_base_weak))
    if vwap_diff <= D_ZERO:
        score_short += Decimal(str(config.trend_vwap_bonus))
    if rvol >= Decimal(str(config.trend_rvol_thresh)):
        score_short += Decimal(str(config.trend_rvol_bonus))
    if rs <= Decimal(str(config.trend_short_rs_strong)):
        score_short += Decimal(str(config.trend_rs_strong_bonus))
    elif rs <= Decimal(str(config.trend_short_rs_weak)):
        score_short += Decimal(str(config.trend_rs_weak_bonus))
    out["trend_short"] = clamp_score(score_short)

    # Exhaustion risk (extension from dma20 + high RVOL) - using Decimal for precise calculations
    ext = abs(last - dma20) / last if last != D_ZERO else D_ZERO
    exh = Decimal(str(config.exhaustion_base))
    ext_min = Decimal(str(config.exhaustion_ext_min))
    ext_max = Decimal(str(config.exhaustion_ext_max))

    if ext >= ext_min:
        # Linear scaling from ext_min to ext_max -> adds ext_range on top of ext_base
        # Original: 60 + 20 * min(1.0, (ext - 0.05) / 0.05)
        # This gives: 60->80 as ext goes from 5% to 10%
        ext_base = Decimal(str(config.exhaustion_ext_base))
        ext_range = Decimal(str(config.exhaustion_ext_range))
        scale_factor = min(D_ONE, (ext - ext_min) / (ext_max - ext_min))
        exh = ext_base + ext_range * scale_factor

    if rvol >= Decimal(str(config.exhaustion_rvol_thresh)):
        exh += Decimal(str(config.exhaustion_rvol_bonus))

    out["exhaustion"] = clamp_score(exh)

    return out
