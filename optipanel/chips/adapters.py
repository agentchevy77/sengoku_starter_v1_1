from __future__ import annotations


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _wavg(pairs: tuple[tuple[float, float], ...]) -> float:
    total = 0.0
    weight_sum = 0.0
    for value, weight in pairs:
        total += float(value) * weight
        weight_sum += weight
    return total / weight_sum if weight_sum else 0.0


def micro_to_prob(chips: dict[str, int]) -> dict[str, int]:
    """Map structural microchips into probability-chip space."""

    don = float(chips.get("donchian", 0))
    trend = float(chips.get("trend_dma", 0))
    support = float(chips.get("support_def", 0))
    resistance = float(chips.get("res_clear", 0))
    rvol = float(chips.get("rvol", 50))
    rel_strength = float(chips.get("rs", 50))
    vwap = float(chips.get("vwap", 50))

    breakout_up = _wavg(((don, 0.35), (resistance, 0.25), (rel_strength, 0.20), (rvol, 0.10), (vwap, 0.10)))
    trend_long = _wavg(((trend, 0.55), (rel_strength, 0.30), (vwap, 0.15)))
    trend_short = 100.0 - trend_long
    rejection_down = _wavg(((100.0 - resistance, 0.70), (100.0 - vwap, 0.30)))
    breakdown_down = _wavg(((100.0 - support, 0.50), (100.0 - don, 0.25), (100.0 - rel_strength, 0.25)))
    bounce_up = support
    exhaustion = _wavg(((abs(trend - 50.0) * 2.0, 0.60), (rvol, 0.40)))

    return {
        "breakout_up": int(round(_clip(breakout_up))),
        "trend_long": int(round(_clip(trend_long))),
        "trend_short": int(round(_clip(trend_short))),
        "rejection_down": int(round(_clip(rejection_down))),
        "breakdown_down": int(round(_clip(breakdown_down))),
        "bounce_up": int(round(_clip(bounce_up))),
        "exhaustion": int(round(_clip(exhaustion))),
    }
