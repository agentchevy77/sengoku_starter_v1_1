"""60-minute probability chips helper."""

from __future__ import annotations

from collections.abc import Mapping

from optipanel.probs import coerce_features, compute_chips


def compute_chips_h60(features: Mapping[str, object]) -> dict[str, int]:
    """Return 60-minute timeframe chips."""

    bundle = coerce_features(features)
    return compute_chips(bundle, "60m")
