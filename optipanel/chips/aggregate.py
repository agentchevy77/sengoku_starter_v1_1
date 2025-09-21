from __future__ import annotations


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
