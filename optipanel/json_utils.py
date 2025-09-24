"""JSON helpers that favour orjson with transparent fallbacks.

The module mirrors a small subset of ``json``'s interface (``dumps``, ``dump``,
``loads`` and ``JSONDecodeError``) so existing call sites can import it as a
stand-in for the standard library while benefiting from the faster ``orjson``
codec when available.
"""

from __future__ import annotations

import json as _std_json
from typing import IO, Any, cast

try:  # pragma: no cover - availability depends on installation
    import orjson
except ImportError:  # pragma: no cover - exercised on platforms without orjson
    _HAS_ORJSON = False
    JSONDecodeError: type[Exception] = _std_json.JSONDecodeError
else:  # pragma: no cover - trivial branch once imported
    _HAS_ORJSON = True
    JSONDecodeError = cast(type[Exception], orjson.JSONDecodeError)


def _should_fallback(indent: int | None) -> bool:
    """Return True when we need the stdlib for formatting options."""

    if indent is None:
        return False
    # ``orjson`` only supports two-space indentation via OPT_INDENT_2.
    return indent not in {0, 2}


def _orjson_options(sort_keys: bool, indent: int | None) -> int:
    option = 0
    if not _HAS_ORJSON:
        return option
    if sort_keys:
        option |= orjson.OPT_SORT_KEYS
    if indent == 2:
        option |= orjson.OPT_INDENT_2
    return option


def dumps(obj: Any, *, sort_keys: bool = False, indent: int | None = None) -> str:
    """Serialize ``obj`` into JSON, preferring ``orjson`` when possible."""

    if not _HAS_ORJSON or _should_fallback(indent):
        return _std_json.dumps(obj, sort_keys=sort_keys, indent=indent)
    return orjson.dumps(obj, option=_orjson_options(sort_keys, indent)).decode()


def dump(obj: Any, fp: IO[str], *, sort_keys: bool = False, indent: int | None = None) -> str:
    """Serialize ``obj`` to ``fp`` returning the text payload written."""

    text = dumps(obj, sort_keys=sort_keys, indent=indent)
    fp.write(text)
    return text


def loads(data: str | bytes | bytearray) -> Any:
    """Deserialize JSON data using ``orjson`` when present."""

    if not _HAS_ORJSON:
        return _std_json.loads(data)
    return orjson.loads(data)


__all__ = ["dumps", "dump", "loads", "JSONDecodeError"]
