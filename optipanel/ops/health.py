"""Operational health helpers (Stage 3 — Hardening & Observability).

Utilities here keep the runtime lightweight while improving the signal we
surface to operators: a single call to ``collect_health`` gives us a durable
snapshot of the TWS session, and ``write_health`` persists it safely for file
watchers or dashboards.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from optipanel import json_utils as json
from optipanel.runtime.watchdog import WatchdogSnapshot


def _safe_call(method_name: str, obj: Any, *args: Any, **kwargs: Any) -> Any:
    method = getattr(obj, method_name, None)
    if not callable(method):  # pragma: no cover - defensive guard
        raise AttributeError(f"{obj!r} has no callable {method_name}")
    return method(*args, **kwargs)


def collect_health(
    fetcher: Any,
    *,
    watchdog: Any | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a health payload derived from ``fetcher.handshake_test``.

    ``fetcher`` is expected to expose ``cfg`` (with host/port/client_id) and
    ``handshake_test``.  Any exceptions are captured and attached to the
    payload instead of bubbling out.
    """

    cfg = getattr(fetcher, "cfg", None)
    payload: dict[str, Any] = {
        "ts": time.time(),
        "ok": False,
        "host": getattr(cfg, "host", None),
        "port": getattr(cfg, "port", None),
        "client_id": getattr(cfg, "client_id", None),
    }

    try:
        handshake = _safe_call("handshake_test", fetcher)
        payload["handshake"] = handshake or {}
        payload["ok"] = bool(handshake and handshake.get("handshake") == "ok")
        payload["errors"] = list(handshake.get("errors", [])) if isinstance(handshake, Mapping) else []
    except Exception as exc:
        payload["errors"] = [f"{type(exc).__name__}: {exc}"]
    else:
        if payload["ok"]:
            payload.setdefault("errors", [])
    # Optional watchdog snapshot
    if watchdog is not None:
        try:
            snap = watchdog.snapshot()
            if isinstance(snap, WatchdogSnapshot):
                payload["watchdog"] = snap.as_dict()
            else:  # support duck-typed snapshot objects
                payload["watchdog"] = dict(snap)
        except Exception as exc:  # pragma: no cover - defensive path
            payload.setdefault("errors", []).append(f"watchdog: {type(exc).__name__}: {exc}")
    if extra:
        payload.update(dict(extra))
    return payload


def write_health(path: str | os.PathLike[str], data: Mapping[str, Any]) -> Path:
    """Write ``data`` to ``path`` atomically (JSON, UTF-8)."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target.with_suffix(target.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    tmp_path.replace(target)
    return target
