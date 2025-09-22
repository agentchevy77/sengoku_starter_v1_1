from __future__ import annotations

from typing import Any

from .adapters import micro_to_prob

_TF_SYNONYMS = {
    "M15": ("15m", "m15", "M15"),
    "H1": ("60m", "1h", "h1", "H1"),
    "D": ("1d", "d1", "day", "daily", "D"),
}


def _select_features(features: dict[str, Any], tf: str) -> dict[str, Any]:
    bundles = features.get("bundles") if isinstance(features, dict) else None
    if isinstance(bundles, dict):
        for alias in _TF_SYNONYMS.get(tf, (tf,)):
            candidate = bundles.get(alias)
            if isinstance(candidate, dict):
                return dict(candidate)
    return dict(features)


def compute_chips_by_tf(features: dict[str, Any], mode: str = "prob") -> dict[str, dict[str, int]]:
    """Return per-timeframe probability-style chips keyed by M15/H1/D."""

    normalized = (mode or "prob").lower()
    if normalized == "prob":
        from optipanel.chips.prob_tf import (
            compute_probchips_daily,
            compute_probchips_h60,
            compute_probchips_m15,
        )

        base = dict(features)
        return {
            "M15": compute_probchips_m15(_select_features(features, "M15"), base),
            "H1": compute_probchips_h60(_select_features(features, "H1"), base),
            "D": compute_probchips_daily(_select_features(features, "D"), base),
        }

    if normalized == "micro":
        from optipanel.chips.daily import compute_daily_microchips
        from optipanel.chips.h60 import compute_h60_microchips
        from optipanel.chips.m15 import compute_m15_microchips

        return {
            "M15": micro_to_prob(compute_m15_microchips(_select_features(features, "M15"))),
            "H1": micro_to_prob(compute_h60_microchips(_select_features(features, "H1"))),
            "D": micro_to_prob(compute_daily_microchips(_select_features(features, "D"))),
        }

    raise ValueError("mode must be 'prob' or 'micro'")
