from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_lock = threading.RLock()
_counters: dict[str, int] = {}
_timers: dict[str, dict[str, float]] = {}


def record(name: str, inc: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + inc


@contextmanager
def timer(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        with _lock:
            slot = _timers.setdefault(
                name,
                {"count": 0.0, "total_ms": 0.0, "min_ms": elapsed_ms, "max_ms": elapsed_ms},
            )
            slot["count"] += 1.0
            slot["total_ms"] += elapsed_ms
            slot["min_ms"] = min(slot["min_ms"], elapsed_ms)
            slot["max_ms"] = max(slot["max_ms"], elapsed_ms)


def snapshot() -> dict[str, Any]:
    with _lock:
        timers: dict[str, dict[str, float]] = {}
        for name, stats in _timers.items():
            count = stats["count"] or 1.0
            timers[name] = {
                "count": int(stats["count"]),
                "total_ms": stats["total_ms"],
                "avg_ms": stats["total_ms"] / count,
                "min_ms": stats["min_ms"],
                "max_ms": stats["max_ms"],
            }
        return {"counters": dict(_counters), "timers": timers}


def export_json(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot(), indent=2, sort_keys=True), encoding="utf-8")
    return target


def reset() -> None:
    with _lock:
        _counters.clear()
        _timers.clear()
