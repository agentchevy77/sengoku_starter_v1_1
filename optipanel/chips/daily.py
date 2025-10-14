"""Microchip-driven daily probability chips."""

from __future__ import annotations

from typing import Any

from .lib import probs_from_microchips
from .micro import compute_microchips_daily


def compute_daily_microchips(features: dict[str, Any]) -> dict[str, int]:
    """Return raw microchips for the daily timeframe."""

    return compute_microchips_daily(features)


def compute_chips_daily(features: dict[str, Any]) -> dict[str, int]:
    """Compute daily probability chips using microchips."""

    micro = compute_microchips_daily(features)
    return probs_from_microchips(micro)
