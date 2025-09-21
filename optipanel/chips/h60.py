"""Microchip-driven 60-minute probability chips."""

from __future__ import annotations

from typing import Any

from .lib import microchips_from_features, probs_from_microchips


def compute_h60_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchips for the 60-minute timeframe."""

    return microchips_from_features(features)


def compute_chips_h60(features: dict[str, Any]) -> dict[str, int]:
    """Compute 60-minute probability chips using microchips."""

    micro = microchips_from_features(features)
    return probs_from_microchips(micro)
