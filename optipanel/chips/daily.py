"""Daily probability chips helper."""

from __future__ import annotations

from collections.abc import Mapping

from optipanel.probs import coerce_features, compute_chips


def compute_chips_daily(features: Mapping[str, object]) -> dict[str, int]:
    """Return daily timeframe chips."""

    bundle = coerce_features(features)
    return compute_chips(bundle, "1d")
