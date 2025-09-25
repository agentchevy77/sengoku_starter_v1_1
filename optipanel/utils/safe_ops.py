"""Safe operations utility module for robust error handling.

This module provides thread-safe, type-safe utilities to prevent common
runtime errors like division by zero, unchecked indexing, and parsing failures.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
_EPSILON = 1e-9


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: The dividend
        denominator: The divisor
        default: Value to return if division by zero

    Returns:
        Result of division or default value
    """
    if abs(denominator) < _EPSILON:
        return default
    return numerator / denominator


def safe_index(seq: Sequence[T], index: int, default: T | None = None) -> T | None:
    """Safely access a sequence by index, returning default if out of bounds.

    Args:
        seq: The sequence to index into
        index: The index to access
        default: Value to return if index is out of bounds

    Returns:
        Element at index or default value
    """
    try:
        if -len(seq) <= index < len(seq):
            return seq[index]
    except (IndexError, TypeError):
        pass
    return default


def safe_int_env(key: str, default: int = 0) -> int:
    """Safely parse an integer from environment variable.

    Args:
        key: Environment variable name
        default: Default value if parsing fails

    Returns:
        Parsed integer or default value
    """
    try:
        value = os.getenv(key)
        if value is not None:
            return int(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse int from {key}={value}: {e}")
    return default


def safe_float_env(key: str, default: float = 0.0) -> float:
    """Safely parse a float from environment variable.

    Args:
        key: Environment variable name
        default: Default value if parsing fails

    Returns:
        Parsed float or default value
    """
    try:
        value = os.getenv(key)
        if value is not None:
            return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse float from {key}={value}: {e}")
    return default


def safe_json_loads(text: str, default: dict | None = None) -> dict[str, Any]:
    """Safely parse JSON text, returning default on error.

    Args:
        text: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    if default is None:
        default = {}
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        logger.warning(f"JSON parsed to non-dict type: {type(result)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {e}")
    return default


def safe_json_load_file(path: Path, default: dict | None = None) -> dict[str, Any]:
    """Safely load and parse JSON from file.

    Args:
        path: Path to JSON file
        default: Default value if loading/parsing fails

    Returns:
        Parsed JSON or default value
    """
    if default is None:
        default = {}
    try:
        text = path.read_text(encoding="utf-8")
        return safe_json_loads(text, default)
    except OSError as e:
        logger.error(f"Failed to read {path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading {path}: {e}")
    return default


def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dictionaries.

    Args:
        data: The dictionary to navigate
        *keys: Sequence of keys to traverse
        default: Value to return if path doesn't exist

    Returns:
        Value at path or default

    Example:
        >>> d = {"a": {"b": {"c": 42}}}
        >>> safe_get_nested(d, "a", "b", "c")  # Returns 42
        >>> safe_get_nested(d, "a", "x", "y", default=0)  # Returns 0
    """
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def safe_percentage(part: float, whole: float, default: float = 0.0) -> float:
    """Calculate percentage safely, handling division by zero.

    Args:
        part: The numerator (part of whole)
        whole: The denominator (total)
        default: Value to return if whole is zero

    Returns:
        Percentage (0-100) or default value
    """
    if abs(whole) < _EPSILON:
        return default
    return (part / whole) * 100.0


def safe_list_stats(values: list[float]) -> dict[str, float]:
    """Calculate statistics safely for a list of values.

    Args:
        values: List of numeric values

    Returns:
        Dictionary with avg, min, max, p50, p95 (all 0 if empty)
    """
    if not values:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    return {
        "avg": sum(values) / n,
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "p50": sorted_vals[n // 2],
        "p95": sorted_vals[min(int(n * 0.95), n - 1)],
    }


# Re-export for convenience
__all__ = [
    "safe_divide",
    "safe_index",
    "safe_int_env",
    "safe_float_env",
    "safe_json_loads",
    "safe_json_load_file",
    "safe_get_nested",
    "safe_percentage",
    "safe_list_stats",
]
