"""Structured event logging for Sengoku operations."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any

from optipanel import json_utils as json


class DurabilityLevel(Enum):
    """Log durability levels for performance/safety trade-offs.

    PERFORMANCE: No flush, fastest but may lose data on crash (legacy behavior)
    STANDARD: Flush to OS buffer, protects against app crash
    PARANOID: Flush + fsync, protects against OS crash/power loss
    """

    PERFORMANCE = 0  # No flush (legacy behavior for backward compat)
    STANDARD = 1  # flush() only - protects against app crash
    PARANOID = 2  # flush() + fsync() - protects against OS crash


class EventLogger:
    """Append structured events (JSONL) grouped by UTC day.

    Files land in ``<log_dir>/events-YYYYMMDD.jsonl`` and are safe to tail or
    ship to an external collector.  Use for watchdog transitions, recon
    decisions, alert emissions, etc.
    """

    def __init__(
        self,
        log_dir: str | None = None,
        durability: DurabilityLevel | None = None,
    ) -> None:
        """Initialize EventLogger with configurable durability.

        Args:
            log_dir: Directory for log files
            durability: Durability level (defaults to STANDARD for safety)
        """
        root = log_dir or os.getenv("SENGOKU_LOG_DIR") or "./runs"
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

        # Default to STANDARD for safety, can override via env var
        if durability is None:
            env_level = os.getenv("SENGOKU_LOG_DURABILITY", "STANDARD").upper()
            try:
                self._durability = DurabilityLevel[env_level]
            except KeyError:
                self._durability = DurabilityLevel.STANDARD
        else:
            self._durability = durability

        # Track flush failures for monitoring
        self._flush_failures = 0
        self._fsync_failures = 0

    def _path_for_today(self) -> Path:
        day = time.strftime("%Y%m%d", time.gmtime())
        return self._root / f"events-{day}.jsonl"

    def _safe_flush(self, handle) -> bool:
        """Safely flush file handle with error tracking.

        Returns:
            True if flush successful, False otherwise
        """
        try:
            handle.flush()
            return True
        except OSError as e:
            self._flush_failures += 1
            self._log_error(f"Flush failed: {e}")
            return False

    def _safe_fsync(self, handle) -> bool:
        """Safely fsync file handle with error tracking.

        Returns:
            True if fsync successful, False otherwise
        """
        try:
            os.fsync(handle.fileno())
            return True
        except OSError as e:
            self._fsync_failures += 1
            self._log_error(f"Fsync failed: {e}")
            return False

    def _log_error(self, message: str) -> None:
        """Log internal errors to stderr as fallback."""
        try:
            sys.stderr.write(f"EventLogger error: {message}\n")
        except Exception:
            pass  # Ultimate fallback - silent failure

    def emit(self, kind: str, payload: Mapping[str, Any]) -> Path:
        """Write one event line with configurable durability.

        Bug #24 FIX: Added flush() and optional fsync() to prevent data loss.
        The original implementation left data in OS buffers that would be lost
        on application crash. This fix ensures data durability based on the
        configured level.

        Returns:
            Path written to, or fallback path if write failed
        """
        record: dict[str, Any] = {"ts": time.time(), "kind": str(kind)}
        record.update(dict(payload))

        path = self._path_for_today()
        write_success = False

        try:
            with path.open("a", encoding="utf-8") as handle:
                # Write the data
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")

                # Apply durability guarantees based on level
                if self._durability == DurabilityLevel.STANDARD:
                    # Flush to OS buffer - protects against app crash
                    self._safe_flush(handle)
                elif self._durability == DurabilityLevel.PARANOID:
                    # Flush + fsync - protects against OS crash/power loss
                    if self._safe_flush(handle):
                        self._safe_fsync(handle)
                # DurabilityLevel.PERFORMANCE skips flush (legacy behavior)

                write_success = True
        except Exception as e:
            self._log_error(f"Failed to write event: {e}")

            # Fallback: Try to write to stderr if file write fails
            if not write_success:
                try:
                    fallback_msg = f"FALLBACK_LOG: {json.dumps(record, sort_keys=True)}\n"
                    sys.stderr.write(fallback_msg)
                except Exception:
                    pass  # Ultimate failure - data lost

        return path

    @property
    def flush_failures(self) -> int:
        """Get count of flush failures for monitoring."""
        return self._flush_failures

    @property
    def fsync_failures(self) -> int:
        """Get count of fsync failures for monitoring."""
        return self._fsync_failures

    @property
    def durability_level(self) -> DurabilityLevel:
        """Get current durability level."""
        return self._durability
