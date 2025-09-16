from __future__ import annotations
from typing import Dict, Any

def _clamp_int(x: float) -> int:
    x = int(round(x))
    return 0 if x < 0 else 100 if x > 100 else x

def _pct_gap_above(last: float, level: float) -> float:
    if last <= 0: return 1e9
    return (level - last) / last

def _pct_gap_below(last: float, level: float) -> float:
    if last <= 0: return 1e9
    return (last - level) / last

def compute_setups(features: Dict[str, Any]) -> Dict[str, int]:
    """
    Deterministic 0..100 scores for:
    breakout_up, breakdown_down, bounce_up, rejection_down, trend_long, trend_short, exhaustion.
    Uses: last, dma20, support, resistance, rvol, rs_strength, vwap_diff (optional; default 0.0).
    """
    last        = float(features["last"])
    dma20       = float(features["dma20"])
    support     = float(features["support"])
    resistance  = float(features["resistance"])
    rvol        = float(features.get("rvol", 1.0))
    rs          = float(features.get("rs_strength", 0.0))
    vwap_diff   = float(features.get("vwap_diff", 0.0))

    out: Dict[str, int] = {}

    # Breakout up
    gap = _pct_gap_above(last, resistance)
    if gap <= 0:       base = 85
    elif gap <= 0.01:  base = 60 + 25 * (1 - gap / 0.01)  # 60..85 closer
    else:              base = 30
    bonus = (10 if rvol >= 1.2 else 0) + (10 if rs >= 0.1 else 0) + (5 if last >= dma20 else 0)
    out["breakout_up"] = _clamp_int(base + bonus)

    # Breakdown down
    near_sup = _pct_gap_below(last, support)  # >=0 when above support
    if last < support:    base = 85
    elif near_sup <= 0.01:base = 60 + 25 * (1 - max(0.0, near_sup) / 0.01)
    else:                 base = 30
    bonus = (10 if rvol >= 1.2 else 0) + (10 if rs <= -0.1 else 0) + (5 if last < dma20 else 0)
    out["breakdown_down"] = _clamp_int(base + bonus)

    # Bounce up (defend support)
    if last >= support:
        near = max(0.0, near_sup)
        base = 50 + (20 * (1 - near / 0.01)) if near <= 0.01 else 35
        bonus = (10 if last >= dma20 else 0) + (5 if rs >= 0.0 else 0) + (5 if rvol >= 1.0 else 0)
        out["bounce_up"] = _clamp_int(base + bonus)
    else:
        out["bounce_up"] = _clamp_int(20)

    # Rejection down (fail at resistance)
    if last <= resistance:
        near = max(0.0, _pct_gap_above(last, resistance))
        base = 45 + (15 * (1 - near / 0.01)) if near <= 0.01 else 30
        malus = (10 if last < dma20 else 0) + (10 if rs <= 0.0 else 0) + (5 if rvol >= 1.0 else 0)
        out["rejection_down"] = _clamp_int(base + malus)
    else:
        out["rejection_down"] = _clamp_int(25)

    # Trend continuation long/short
    score_long  = 55 if last >= dma20 else 25
    score_long += 10 if vwap_diff >= 0 else 0
    score_long += 10 if rvol >= 1.2 else 0
    score_long += 15 if rs   >= 0.1 else (5 if rs >= 0 else 0)
    out["trend_long"] = _clamp_int(score_long)

    score_short  = 55 if last < dma20 else 25
    score_short += 10 if vwap_diff <= 0 else 0
    score_short += 10 if rvol >= 1.2 else 0
    score_short += 15 if rs   <= -0.1 else (5 if rs <= 0 else 0)
    out["trend_short"] = _clamp_int(score_short)

    # Exhaustion risk (extension from dma20 + high RVOL)
    ext = abs(last - dma20) / last if last else 0.0
    exh = 30
    if ext >= 0.05:
        exh = 60 + 20 * min(1.0, (ext - 0.05) / 0.05)  # 5–10% -> 60–80
    if rvol >= 1.5:
        exh += 10
    out["exhaustion"] = _clamp_int(exh)

    return out
