from __future__ import annotations

from typing import Any


def _clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    rounded = int(round(value))
    if rounded < lo:
        return lo
    if rounded > hi:
        return hi
    return rounded


def aggregate_chips(
    chips_by_tf: dict[str, dict[str, int]],
    weights: dict[str, float] | None = None,
) -> dict[str, int]:
    """Weighted, normalized merge of per-timeframe chips (0..100)."""

    if not chips_by_tf:
        return {}

    all_keys: set[str] = set()
    for tf_map in chips_by_tf.values():
        if isinstance(tf_map, dict):
            all_keys.update(tf_map.keys())

    out: dict[str, int] = {}
    for key in sorted(all_keys):
        numerator = 0.0
        denom = 0.0
        for tf, chips in chips_by_tf.items():
            if not isinstance(chips, dict) or key not in chips:
                continue
            w = 1.0
            if weights is not None:
                w = float(weights.get(tf, 1.0))
            if w <= 0.0:
                continue
            numerator += w * float(chips[key])
            denom += w
        if denom > 0.0:
            out[key] = _clamp(numerator / denom)
    return out


def recon_score(agg: dict[str, int]) -> int:
    """Scout score: avg(breakout_up, trend_long) - 0.5*rejection_down."""

    breakout = float(agg.get("breakout_up", agg.get("breakout_up_prob", 0)))
    trend = float(agg.get("trend_long", agg.get("trend_long_prob", 0)))
    rejection = float(agg.get("rejection_down", agg.get("rejection_down_prob", 0)))
    attack = (breakout + trend) / 2.0
    score = attack - 0.5 * rejection
    return _clamp(score)


def summarize_chips(chips_by_tf: dict[str, dict[str, int]] | None) -> dict[str, dict[str, int]]:
    """Return compact per-timeframe summaries for dashboards."""

    if not chips_by_tf:
        return {}

    summary: dict[str, dict[str, int]] = {}
    for tf, chips in chips_by_tf.items():
        if not isinstance(chips, dict):
            continue

        breakout_up = int(chips.get("breakout_up", chips.get("breakout_up_prob", 0)))
        breakdown_down = int(chips.get("breakdown_down", chips.get("breakdown_down_prob", 0)))
        trend_long = int(chips.get("trend_long", chips.get("trend_long_prob", 0)))
        trend_short = int(chips.get("trend_short", chips.get("trend_short_prob", 0)))
        bounce_up = int(chips.get("bounce_up", chips.get("bounce_up_prob", 0)))
        rejection_down = int(chips.get("rejection_down", chips.get("rejection_down_prob", 0)))

        position = max(0, min(100, 50 + (breakout_up - breakdown_down) // 2))
        momentum = max(trend_long, trend_short)
        supply = max(bounce_up, rejection_down)

        summary[str(tf)] = {
            "position": position,
            "momentum": momentum,
            "supply": supply,
        }

    return summary


def compute_sustainment(chips_by_tf: dict[str, dict[str, int]] | None) -> dict[str, Any]:
    """Derive sustainability vs fakeout risk from probability chips."""

    if not chips_by_tf:
        return {"sustainability": 50, "fakeout_risk": 50, "debug": {}}

    weights = {"D": 0.5, "H1": 0.3, "M15": 0.2}
    sustain_sum = 0.0
    risk_sum = 0.0
    w_sum = 0.0
    debug: dict[str, Any] = {}

    for tf, chips in chips_by_tf.items():
        if not isinstance(chips, dict):
            continue
        canon = tf.upper()
        w = weights.get(canon, 0.0)
        if w <= 0.0:
            continue

        trend = float(chips.get("trend_long", chips.get("trend_long_prob", 0)))
        counter = float(chips.get("trend_short", chips.get("trend_short_prob", 0)))
        breakout = float(chips.get("breakout_up", chips.get("breakout_up_prob", 0)))
        fake_break = float(chips.get("rejection_down", chips.get("rejection_down_prob", 0)))
        support = float(chips.get("bounce_up", chips.get("bounce_up_prob", 0)))
        breakdown = float(chips.get("breakdown_down", chips.get("breakdown_down_prob", 0)))

        sustain_component = 0.5 * (trend + breakout) + 0.3 * support
        risk_component = 0.5 * max(counter, breakdown) + 0.3 * fake_break

        sustain_sum += sustain_component * w
        risk_sum += risk_component * w
        w_sum += w

        debug[canon] = {
            "trend": trend,
            "counter": counter,
            "breakout": breakout,
            "fake_break": fake_break,
            "support": support,
            "breakdown": breakdown,
            "sustain_component": sustain_component,
            "risk_component": risk_component,
            "weight": w,
        }

    sustainability = _clamp(sustain_sum / w_sum if w_sum else 50.0)
    fakeout_risk = _clamp(risk_sum / w_sum if w_sum else 50.0)

    return {
        "sustainability": sustainability,
        "fakeout_risk": fakeout_risk,
        "debug": debug,
    }
