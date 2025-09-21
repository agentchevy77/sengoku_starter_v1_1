"""Microchip-driven 15-minute probability chips."""

from __future__ import annotations

from typing import Any

from .lib import microchips_from_features, probs_from_microchips


def compute_chips_m15(features: dict[str, Any]) -> dict[str, int]:
    """Compute 15m probability chips via microchip heuristics."""

    micro = microchips_from_features(features)
    return probs_from_microchips(micro)
