"""Core probability chips computation for a single timeframe."""

from __future__ import annotations

import math
import os
from typing import Any

from optipanel.setups.engine import compute_setups

from .spec import VALID_TIMEFRAMES, coerce_features

_SLOPE = {"15m": 9.0, "60m": 11.0, "1d": 13.0}


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _prob(score_0_100: float, bias: float, slope: float) -> int:
    z = (score_0_100 - 50.0) / max(1e-6, slope) + bias
    p = _sigmoid(z) * 100.0
    p = int(round(p))
    return min(100, max(0, p))


def _gap_above(last: float, level: float) -> float:
    return (level - last) / last if last > 0 else 0.0


def _gap_below(last: float, level: float) -> float:
    return (last - level) / last if last > 0 else 0.0


def _evidence_bias(feat: dict[str, float], chip: str) -> float:
    rs = feat["rs_strength"]
    above_dma = 1.0 if feat["last"] >= feat["dma20"] else -1.0
    don = (feat["donchian_pos"] - 0.5) * 2.0
    vwap = feat["vwap_diff"] * 10.0
    obv = feat["obv_slope"]
    cad = feat["chaikin_ad"]
    clv = feat["clv"]
    vconf = feat["vwap_confluence"]

    if chip == "trend_long":
        return 0.5 * rs + 0.35 * above_dma + 0.25 * don + 0.15 * obv
    if chip == "trend_short":
        return -(0.5 * rs + 0.35 * above_dma + 0.25 * don + 0.15 * obv)

    if chip == "breakout_up":
        return 0.5 * don + 0.35 * rs + 0.25 * vwap + 0.1 * cad
    if chip == "breakdown_down":
        return -(0.5 * don + 0.35 * rs + 0.25 * vwap + 0.1 * cad)

    if chip == "bounce_up":
        near = _gap_below(feat["last"], feat["support"])
        near_score = 1.0 if (feat["last"] >= feat["support"] and near <= 0.01) else -0.5
        return 0.5 * near_score + 0.2 * obv + 0.1 * clv + 0.1 * vconf

    if chip == "rejection_down":
        near = _gap_above(feat["last"], feat["resistance"])
        near_score = 1.0 if (feat["resistance"] >= feat["last"] and near <= 0.01) else -0.5
        return 0.5 * near_score - 0.2 * obv - 0.1 * clv - 0.1 * vconf

    if chip == "sustainment":
        return 0.4 * obv + 0.35 * cad + 0.25 * vconf
    if chip == "fakeout":
        return -(0.4 * obv + 0.35 * cad + 0.25 * vconf)

    return 0.0


def _timeframe_slope(t: str) -> float:
    return _SLOPE.get(t, 11.0)


def compute_chips(features: dict[str, Any], timeframe: str) -> dict[str, int]:
    """Return probability chips for timeframe in {'15m','60m','1d'}.

    '5m' is feature gated via SENGOKU_CHIPS_5M=1.
    """

    if timeframe == "5m" and os.getenv("SENGOKU_CHIPS_5M") != "1":
        raise ValueError("5m chips are disabled. Set SENGOKU_CHIPS_5M=1 to enable.")

    if timeframe not in VALID_TIMEFRAMES and timeframe != "5m":
        raise ValueError(f"invalid timeframe: {timeframe}")

    feat = coerce_features(features)
    base = compute_setups(feat)
    slope = _timeframe_slope("15m" if timeframe == "5m" else timeframe)

    chips: dict[str, int] = {}

    chips["breakout_up_prob"] = _prob(base["breakout_up"], _evidence_bias(feat, "breakout_up"), slope)
    chips["breakdown_down_prob"] = _prob(base["breakdown_down"], _evidence_bias(feat, "breakdown_down"), slope)
    chips["bounce_up_prob"] = _prob(base["bounce_up"], _evidence_bias(feat, "bounce_up"), slope)
    chips["rejection_down_prob"] = _prob(base["rejection_down"], _evidence_bias(feat, "rejection_down"), slope)
    chips["trend_long_prob"] = _prob(base["trend_long"], _evidence_bias(feat, "trend_long"), slope)
    chips["trend_short_prob"] = _prob(base["trend_short"], _evidence_bias(feat, "trend_short"), slope)

    sustain_bias = _evidence_bias(feat, "sustainment")
    fakeout_bias = _evidence_bias(feat, "fakeout")
    sustain_base = max(0, 100 - base.get("exhaustion", 50))
    chips["sustainment_prob"] = _prob(sustain_base, sustain_bias, slope)
    chips["fakeout_risk_prob"] = _prob(base.get("exhaustion", 50), fakeout_bias, slope)

    return chips
