"""Aggregate probability chips across timeframes."""

from __future__ import annotations

from typing import Any


def aggregate_chips(
    chips_by_tf: dict[str, dict[str, int]],
    weights: dict[str, float] | None = None,
) -> dict[str, int]:
    """Weighted-average chips across timeframes."""

    if not chips_by_tf:
        return {}

    result: dict[str, int] = {}
    keys: set[str] = set()
    for metrics in chips_by_tf.values():
        keys.update(metrics.keys())

    for key in keys:
        numerator = 0.0
        denom = 0.0
        for tf, metrics in chips_by_tf.items():
            if key not in metrics:
                continue
            weight = 1.0
            if weights is not None:
                weight = float(weights.get(tf, 1.0))
            if weight <= 0.0:
                continue
            numerator += float(metrics[key]) * weight
            denom += weight
        if denom > 0.0:
            value = round(numerator / denom)
            value = max(0, min(100, int(value)))
            result[key] = value

    return result


def _values_for_key(out: dict[str, Any], name: str) -> list[int]:
    values: list[int] = []
    if name in out:
        values.append(int(out[name]))
    prob_key = f"{name}_prob"
    if prob_key in out:
        values.append(int(out[prob_key]))
    return values


def recon_score(out: dict[str, int]) -> int:
    """Recon composite: avg(breakout_up, trend_long) - avg(rejection_down)."""

    positives: list[int] = []
    for key in ("breakout_up", "trend_long"):
        positives.extend(_values_for_key(out, key))
    negatives: list[int] = []
    for key in ("rejection_down",):
        negatives.extend(_values_for_key(out, key))

    pos_avg = sum(positives) / len(positives) if positives else 0.0
    neg_avg = sum(negatives) / len(negatives) if negatives else 0.0

    score = pos_avg - neg_avg
    score = max(0.0, min(100.0, score))
    return int(round(score))
