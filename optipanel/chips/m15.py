"""15-minute probability chips helper."""

from __future__ import annotations

from collections.abc import Mapping

from optipanel.probs import coerce_features, compute_chips


def compute_chips_m15(features: Mapping[str, object]) -> dict[str, int]:
    """Return sanitized chips for the 15-minute timeframe."""

    bundle = coerce_features(features)
    return compute_chips(bundle, "15m")
