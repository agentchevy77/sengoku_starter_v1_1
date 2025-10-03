from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from optipanel.utils.decimal_types import (
    D_ZERO,
    to_decimal,
)

_NEUTRAL = {"bull": 50, "bear": 50}


def _as_decimal(value: object) -> Decimal | None:
    """Convert value to Decimal, returning None if invalid."""
    if value is None:
        return None
    result = to_decimal(value, default=None)  # type: ignore
    if result is None:
        return None
    # Check for valid finite value
    if not result.is_finite():
        return None
    return result


def compute_units(features: Mapping[str, object]) -> dict[str, dict[str, int]]:
    """Return battlefield unit strengths based on feature inputs.

    Missing or non-numeric fields fall back to neutral (50/50) distributions
    instead of raising `KeyError` or `TypeError`.

    Uses Decimal arithmetic for precise percentage calculations.
    """

    last = _as_decimal(features.get("last"))
    dma20 = _as_decimal(features.get("dma20"))
    support = _as_decimal(features.get("support"))
    resistance = _as_decimal(features.get("resistance"))
    rvol = _as_decimal(features.get("rvol"))
    rs_strength = _as_decimal(features.get("rs_strength"))

    units: dict[str, dict[str, int]] = {
        "dma20": dict(_NEUTRAL),
        "support": dict(_NEUTRAL),
        "resistance": dict(_NEUTRAL),
        "rvol": dict(_NEUTRAL),
        "rs": dict(_NEUTRAL),
    }

    if last is not None and dma20 is not None:
        if last >= dma20:
            units["dma20"] = {"bull": 70, "bear": 30}
        else:
            units["dma20"] = {"bull": 30, "bear": 70}

    if last is not None and support is not None and last != D_ZERO:
        # Fixed: Handle negative prices (short positions) correctly with Decimal precision
        distance_pct = abs(last - support) / abs(last)
        if distance_pct <= Decimal("0.01"):  # Within 1%
            if last > support:
                units["support"] = {"bull": 75, "bear": 25}
            else:
                units["support"] = {"bull": 25, "bear": 75}
        elif last < support:
            units["support"] = {"bull": 25, "bear": 75}

    if last is not None and resistance is not None and last != D_ZERO:
        # Fixed: Symmetric logic with support, handles negative prices with Decimal precision
        distance_pct = abs(resistance - last) / abs(last)
        if distance_pct <= Decimal("0.01"):  # Within 1%
            if last < resistance:
                units["resistance"] = {"bull": 25, "bear": 75}
            else:
                units["resistance"] = {"bull": 65, "bear": 35}
        elif resistance < last:
            # Price has cleared resistance; bias to bulls.
            units["resistance"] = {"bull": 65, "bear": 35}

    if rvol is not None:
        if rvol >= Decimal("1.2"):
            units["rvol"] = {"bull": 60, "bear": 40}
        elif rvol <= Decimal("0.8"):
            units["rvol"] = {"bull": 40, "bear": 60}

    if rs_strength is not None:
        if rs_strength >= Decimal("0.1"):
            units["rs"] = {"bull": 60, "bear": 40}
        elif rs_strength <= Decimal("-0.1"):
            units["rs"] = {"bull": 40, "bear": 60}

    return units
