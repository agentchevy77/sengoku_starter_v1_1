"""Microchip-driven 15-minute probability chips."""

from __future__ import annotations

from typing import Any

from .lib import probs_from_microchips
from .micro import compute_microchips_m15


def compute_m15_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchip values (0..100 ints)."""

    return compute_microchips_m15(features)


def compute_chips_m15(features: dict[str, Any]) -> dict[str, int]:
    """Compute probability chips for the 15m timeframe using microchips."""

    micro = compute_microchips_m15(features)
    return probs_from_microchips(micro)
