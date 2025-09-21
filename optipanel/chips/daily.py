"""Microchip-driven daily probability chips."""

from __future__ import annotations

from typing import Any

from .lib import microchips_from_features, probs_from_microchips


def compute_daily_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchips for the daily timeframe."""

    return microchips_from_features(features)


def compute_chips_daily(features: dict[str, Any]) -> dict[str, int]:
    """Compute daily probability chips using microchips."""

    micro = microchips_from_features(features)
    return probs_from_microchips(micro)
