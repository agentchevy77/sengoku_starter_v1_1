"""Microchip-driven 15-minute probability chips."""

from __future__ import annotations

from typing import Any

from .lib import microchips_from_features, probs_from_microchips


def compute_m15_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchip values (0..100 ints)."""

    return microchips_from_features(features)


def compute_chips_m15(features: dict[str, Any]) -> dict[str, int]:
    """Compute probability chips for the 15m timeframe using microchips."""

    micro = microchips_from_features(features)
    return probs_from_microchips(micro)
