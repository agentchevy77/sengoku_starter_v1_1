"""Centralized JSON handling utilities, prioritizing orjson for performance."""

import json
import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# Determine if orjson is available
try:
    import orjson

    USE_ORJSON = True
except ImportError:
    orjson = None
    USE_ORJSON = False


def _json_normalizer(obj: Any) -> Any:
    """Normalize types not supported by standard JSON for serialization."""
    if isinstance(obj, Decimal):
        # Convert Decimal to float for JSON compatibility.
        return float(obj)

    # If using standard json, we must raise TypeError for unhandled types.
    if not USE_ORJSON:
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    # If using orjson, we return the object and let orjson handle it if it can.
    return obj


def dumps(data: Any, indent: int | None = None, sort_keys: bool = False, **kwargs) -> str:
    """Serialize data to a JSON formatted string, using orjson if available."""

    # Ensure the normalizer is used if the caller didn't provide their own default
    if "default" not in kwargs:
        kwargs["default"] = _json_normalizer

    if USE_ORJSON:
        # Handle options for orjson
        options = kwargs.pop("option", 0)
        if indent:
            # orjson only supports 2-space indent
            options |= orjson.OPT_INDENT_2
        if sort_keys:
            options |= orjson.OPT_SORT_KEYS

        try:
            # orjson returns bytes, so we decode to utf-8 string.
            return orjson.dumps(data, option=options, **kwargs).decode("utf-8")
        except TypeError as e:
            logger.error("JSON serialization failed (orjson): %s", e)
            raise
    else:
        # Handle options for standard json
        kwargs["indent"] = indent
        kwargs["sort_keys"] = sort_keys

        try:
            return json.dumps(data, **kwargs)
        except TypeError as e:
            logger.error("JSON serialization failed (standard json): %s", e)
            raise


def dump(data: Any, fp, indent: int | None = None, sort_keys: bool = False, **kwargs) -> str:
    """Serialize data and write it to a file-like object."""

    text = dumps(data, indent=indent, sort_keys=sort_keys, **kwargs)
    fp.write(text)
    return text


def loads(data: str | bytes) -> Any:
    """Deserialize JSON data, using orjson if available."""
    if USE_ORJSON:
        try:
            return orjson.loads(data)
        # Generalized exception handling for compatibility
        except Exception as e:
            # Log and raise for consistency
            logger.error("JSON deserialization failed (orjson): %s", e)
            raise

    else:
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error("JSON deserialization failed (standard json): %s", e)
            raise


# Define a consistent JSONDecodeError type for use across the application
JSONDecodeError = orjson.JSONDecodeError if USE_ORJSON and hasattr(orjson, "JSONDecodeError") else json.JSONDecodeError

__all__ = ["dump", "dumps", "loads", "USE_ORJSON", "JSONDecodeError"]
