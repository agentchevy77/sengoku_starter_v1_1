"""Structured event logging for Sengoku operations."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from optipanel import json_utils as json


class EventLogger:
    """Append structured events (JSONL) grouped by UTC day.

    Files land in ``<log_dir>/events-YYYYMMDD.jsonl`` and are safe to tail or
    ship to an external collector.  Use for watchdog transitions, recon
    decisions, alert emissions, etc.
    """

    def __init__(self, log_dir: str | None = None) -> None:
        root = log_dir or os.getenv("SENGOKU_LOG_DIR") or "./runs"
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for_today(self) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime())
        return self._root / f"events-{day}.jsonl"

    def emit(self, kind: str, payload: Mapping[str, Any]) -> Path:
        """Write one event line; returns the path written to."""

        record: dict[str, Any] = {"ts": time.time(), "kind": str(kind)}
        record.update(dict(payload))

        path = self._path_for_today()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
        return path
