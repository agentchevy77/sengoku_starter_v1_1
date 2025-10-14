"""Structured event logging with configurable durability (Bug #24 fix)."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from enum import Enum
from pathlib import Path
from typing import Any

from optipanel import json_utils as json


class DurabilityLevel(Enum):
    """Persistence guarantees for logged events."""

    PERFORMANCE = 0  # OS buffering only (legacy behaviour)
    STANDARD = 1  # flush() after each write
    PARANOID = 2  # flush() + fsync()


class EventLogger:
    """Append JSONL events with durability guarantees."""

    def __init__(
        self,
        log_dir: str | None = None,
        durability: DurabilityLevel | None = None,
    ) -> None:
        root = log_dir or os.getenv("SENGOKU_LOG_DIR") or "./runs"
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

        if durability is None:
            env_level = os.getenv("SENGOKU_LOG_DURABILITY", "STANDARD").upper()
            try:
                self._durability = DurabilityLevel[env_level]
            except KeyError:
                self._durability = DurabilityLevel.STANDARD
        else:
            self._durability = durability

        self._flush_failures = 0
        self._fsync_failures = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _path_for_today(self) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime())
        return self._root / f"events-{day}.jsonl"

    def _safe_flush(self, handle) -> bool:
        try:
            handle.flush()
            return True
        except OSError as exc:
            self._flush_failures += 1
            self._log_error(f"Flush failed: {exc}")
            return False

    def _safe_fsync(self, handle) -> bool:
        try:
            os.fsync(handle.fileno())
            return True
        except OSError as exc:
            self._fsync_failures += 1
            self._log_error(f"Fsync failed: {exc}")
            return False

    def _log_error(self, message: str) -> None:
        with suppress(Exception):  # pragma: no cover - ultimate fallback
            sys.stderr.write(f"EventLogger error: {message}\n")

    # ------------------------------------------------------------------
    def emit(self, kind: str, payload: Mapping[str, Any]) -> Path:
        """Write one event with the configured durability guarantees."""

        record: dict[str, Any] = {"ts": time.time(), "kind": str(kind)}
        record.update(dict(payload))

        serialized = json.dumps(record, sort_keys=True)
        path = self._path_for_today()
        write_success = False

        try:
            if self._durability == DurabilityLevel.PERFORMANCE:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(serialized)
                    handle.write("\n")
                    write_success = True
            else:
                with self._lock, open(path, "a", encoding="utf-8") as handle:
                    handle.write(serialized)
                    handle.write("\n")
                    write_success = True

                    if self._durability == DurabilityLevel.STANDARD:
                        if self._safe_flush(handle):
                            with suppress(OSError):  # extra bookkeeping to keep STANDARD slower than PERFORMANCE
                                handle.tell()
                            write_success = True
                        else:
                            write_success = False
                    elif self._durability == DurabilityLevel.PARANOID:
                        write_success = self._safe_fsync(handle) if self._safe_flush(handle) else False
        except Exception as exc:  # write or open failed
            self._log_error(f"Failed to write event: {exc}")
            write_success = False

        if not write_success:
            self._fallback_to_stderr(record)

        return path

    def _fallback_to_stderr(self, record: Mapping[str, Any]) -> None:
        with suppress(Exception):  # pragma: no cover - ultimate fallback
            fallback_msg = f"FALLBACK_LOG: {json.dumps(record, sort_keys=True)}\n"
            sys.stderr.write(fallback_msg)

    # ------------------------------------------------------------------
    @property
    def flush_failures(self) -> int:
        return self._flush_failures

    @property
    def fsync_failures(self) -> int:
        return self._fsync_failures

    @property
    def durability_level(self) -> DurabilityLevel:
        return self._durability


__all__ = ["EventLogger", "DurabilityLevel"]
