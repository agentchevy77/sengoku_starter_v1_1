"""Microchip-driven 60-minute probability chips."""

from __future__ import annotations

from typing import Any

from .lib import probs_from_microchips
from .micro import compute_microchips_h60


def compute_h60_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchips for the 60-minute timeframe."""

    return compute_microchips_h60(features)


def compute_chips_h60(features: dict[str, Any]) -> dict[str, int]:
    """Compute 60-minute probability chips using microchips."""

    micro = compute_microchips_h60(features)
    return probs_from_microchips(micro)
