from __future__ import annotations
from typing import Dict, Any
from optipanel.battlefield.engine import compute_units
from optipanel.setups.engine import compute_setups

def _clamp_int(x: float) -> int:
    x = int(round(x))
    return 0 if x < 0 else 100 if x > 100 else x

def build_symbol_snapshot(symbol: str, features: Dict[str, Any]) -> Dict[str, Any]:
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
    units  = compute_units(features)
    setups = compute_setups(features)

    # Simple, deterministic composite:
    # bias = (trend_long - trend_short) + (breakout_up - breakdown_down)
    trend_bias   = setups.get("trend_long", 0) - setups.get("trend_short", 0)
    breakout_bias= setups.get("breakout_up", 0) - setups.get("breakdown_down", 0)
    bias = trend_bias + breakout_bias

    score = _clamp_int(50 + 0.5 * bias)

    if score >= 65:
        advice = "attack"
    elif score <= 35:
        advice = "defend"
    else:
        advice = "standby"

    return {
        "symbol": symbol,
        "units": units,
        "setups": setups,
        "score": score,
        "advice": advice,
    }
