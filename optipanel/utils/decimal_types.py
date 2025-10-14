"""Decimal type utilities for financial calculations.

This module provides high-precision arithmetic using Python's Decimal type
to eliminate floating-point rounding errors in financial calculations.

Key Design:
- All financial calculations (prices, percentages, P&L) use Decimal internally
- Input accepts float/int/str, output is Decimal or rounded to appropriate precision
- Constants and common operations centralized for consistency
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# Precision configuration
PRICE_PRECISION = Decimal("0.01")  # 2 decimal places for prices
PERCENTAGE_PRECISION = Decimal("0.0001")  # 4 decimal places for percentages (0.01%)
SCORE_PRECISION = Decimal("1")  # Integer scores

# Common constants as Decimal
D_ZERO = Decimal("0")
D_ONE = Decimal("1")
D_HUNDRED = Decimal("100")
D_EPSILON = Decimal("1e-9")  # For zero checks


def to_decimal(value: Any, default: Decimal = D_ZERO) -> Decimal:
    """Safely convert value to Decimal, handling float/int/str/None.

    Args:
        value: Value to convert (float, int, str, Decimal, or None)
        default: Default value if conversion fails

    Returns:
        Decimal value or default

    Examples:
        >>> to_decimal(10.5)
        Decimal('10.5')
        >>> to_decimal("100.25")
        Decimal('100.25')
        >>> to_decimal(None, Decimal("0"))
        Decimal('0')
    """
    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        # Convert float to string first to avoid float precision issues
        # str(0.1) = "0.1" -> Decimal("0.1") is exact
        # Decimal(0.1) = Decimal('0.1000000000000000055511151231257827021181583404541015625')
        if isinstance(value, float):
            # Handle inf and nan
            if math.isnan(value) or math.isinf(value):
                return default
            value = str(value)
        return Decimal(value)
    except (ValueError, TypeError, ArithmeticError):
        return default


def to_float(value: Decimal) -> float:
    """Convert Decimal to float for display/serialization.

    Args:
        value: Decimal to convert

    Returns:
        Float representation
    """
    return float(value)


def round_price(value: Decimal) -> Decimal:
    """Round to price precision (2 decimal places).

    Args:
        value: Decimal price

    Returns:
        Rounded Decimal
    """
    return value.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)


def round_percentage(value: Decimal) -> Decimal:
    """Round to percentage precision (4 decimal places).

    Args:
        value: Decimal percentage (e.g., 0.1234 for 12.34%)

    Returns:
        Rounded Decimal
    """
    return value.quantize(PERCENTAGE_PRECISION, rounding=ROUND_HALF_UP)


def round_score(value: Decimal) -> int:
    """Round to integer score (0-100).

    Args:
        value: Decimal score

    Returns:
        Integer score
    """
    return int(value.quantize(SCORE_PRECISION, rounding=ROUND_HALF_UP))


def clamp_score(value: Decimal, lo: int = 0, hi: int = 100) -> int:
    """Clamp and round to integer score.

    Args:
        value: Decimal value to clamp
        lo: Minimum score (inclusive)
        hi: Maximum score (inclusive)

    Returns:
        Integer score in range [lo, hi]
    """
    score = round_score(value)
    if score < lo:
        return lo
    if score > hi:
        return hi
    return score


def safe_divide(numerator: Decimal, denominator: Decimal, default: Decimal = D_ZERO) -> Decimal:
    """Safely divide two Decimal values, returning default if denominator is near zero.

    Args:
        numerator: Dividend
        denominator: Divisor
        default: Value to return if division by zero

    Returns:
        Result of division or default
    """
    if abs(denominator) < D_EPSILON:
        return default
    return numerator / denominator


def safe_percentage(part: Decimal, whole: Decimal, default: Decimal = D_ZERO) -> Decimal:
    """Calculate percentage safely with Decimal precision.

    Args:
        part: Numerator
        whole: Denominator
        default: Value to return if whole is zero

    Returns:
        Percentage as Decimal (e.g., 0.05 for 5%)
    """
    if abs(whole) < D_EPSILON:
        return default
    return part / whole


def pct_gap_above(last: Decimal, level: Decimal) -> Decimal:
    """Calculate percentage gap when price is below level.

    Returns positive value indicating how far above the level is.

    Args:
        last: Current price
        level: Target level (resistance)

    Returns:
        Decimal percentage gap
    """
    if last <= D_ZERO:
        return Decimal("1e9")  # Infinity-like value
    return (level - last) / last


def pct_gap_below(last: Decimal, level: Decimal) -> Decimal:
    """Calculate percentage gap when price is above level.

    Returns positive value indicating how far below the level is.

    Args:
        last: Current price
        level: Target level (support)

    Returns:
        Decimal percentage gap
    """
    if last <= D_ZERO:
        return Decimal("1e9")  # Infinity-like value
    return (last - level) / last


def is_finite(value: Decimal) -> bool:
    """Check if Decimal is finite (not NaN or Inf).

    Args:
        value: Decimal to check

    Returns:
        True if finite, False otherwise
    """
    return value.is_finite()


# Provide backward compatibility helpers
__all__ = [
    "to_decimal",
    "to_float",
    "round_price",
    "round_percentage",
    "round_score",
    "clamp_score",
    "safe_divide",
    "safe_percentage",
    "pct_gap_above",
    "pct_gap_below",
    "is_finite",
    "D_ZERO",
    "D_ONE",
    "D_HUNDRED",
    "D_EPSILON",
    "PRICE_PRECISION",
    "PERCENTAGE_PRECISION",
    "SCORE_PRECISION",
]
