from __future__ import annotations

import os
import platform
import socket
import time
from collections.abc import Mapping
from typing import Any


def _ts() -> int:
    return int(time.time())


def _getattr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def get_ibkr_health(fetcher: Any) -> dict[str, Any]:
    """Collect lenient IBKR fetcher diagnostics for health reporting."""

    last_ok = _getattr(fetcher, "last_ok", None)
    last_error = _getattr(fetcher, "last_error", None)
    if last_ok is None and hasattr(fetcher, "last_ok_timestamp"):
        try:
            last_ok = fetcher.last_ok_timestamp()
        except Exception:
            last_ok = None
    if last_error is None and hasattr(fetcher, "last_error_message"):
        try:
            last_error = fetcher.last_error_message()
        except Exception:
            last_error = None

    return {
        "host": _getattr(fetcher.cfg, "host", None),
        "port": _getattr(fetcher.cfg, "port", None),
        "client_id": _getattr(fetcher.cfg, "client_id", None),
        "last_ok": last_ok,
        "last_error": last_error,
        "daily_cache_size": len(_getattr(fetcher, "_daily_cache", {})),
        "ok": last_ok is not None,
    }


def get_runtime_health(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "ts": _ts(),
        "host": socket.gethostname(),
        "py": platform.python_version(),
        "env": {
            "TWS_HOST": os.getenv("SENGOKU_TWS_HOST"),
            "TWS_PORT": os.getenv("SENGOKU_TWS_PORT"),
            "TWS_CLIENT_ID": os.getenv("SENGOKU_TWS_CLIENT_ID"),
        },
    }
    if extra:
        payload.update(dict(extra))
    return payload
