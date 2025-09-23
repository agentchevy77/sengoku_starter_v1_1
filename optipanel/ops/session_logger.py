"""Enhanced session logging with tracking and lifecycle management."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from optipanel.ops.session_logger_safe import SafeSessionLogger, SessionMetadata


class LogRotationManager:
    """Manages log file rotation and retention."""

    def __init__(
        self,
        log_dir: str,
        max_size_mb: int = 100,
        max_age_days: int = 30,
        max_files: int = 100,
    ) -> None:
        """Initialize log rotation manager.

        Args:
            log_dir: Directory containing log files
            max_size_mb: Maximum size per log file before rotation
            max_age_days: Maximum age of log files before deletion
            max_files: Maximum number of log files to keep
        """
        self._log_dir = Path(log_dir)
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._max_age_seconds = max_age_days * 24 * 3600
        self._max_files = max_files

    def should_rotate(self, file_path: Path) -> bool:
        """Check if a file should be rotated."""
        if not file_path.exists():
            return False

        stat = file_path.stat()
        return stat.st_size > self._max_size_bytes

    def rotate_file(self, file_path: Path) -> Path:
        """Rotate a log file by renaming it with a timestamp."""
        if not file_path.exists():
            return file_path

        timestamp = int(time.time() * 1000)
        rotated_name = f"{file_path.stem}.{timestamp}{file_path.suffix}"
        rotated_path = file_path.parent / rotated_name

        file_path.rename(rotated_path)

        # Compress if gzip is available
        try:
            import gzip

            compressed_path = Path(f"{rotated_path}.gz")
            with open(rotated_path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                f_out.write(f_in.read())
            rotated_path.unlink()
            return compressed_path
        except ImportError:
            return rotated_path

    def cleanup_old_files(self) -> list[Path]:
        """Remove old log files based on retention policy."""
        removed = []
        current_time = time.time()

        # Get all log files
        log_files = list(self._log_dir.glob("events-*.jsonl*"))
        log_files.extend(self._log_dir.glob("sengoku_*.log*"))

        # Sort by modification time (oldest first)
        log_files.sort(key=lambda p: p.stat().st_mtime)

        # Remove based on age
        for file_path in log_files:
            stat = file_path.stat()
            age_seconds = current_time - stat.st_mtime

            if age_seconds > self._max_age_seconds:
                file_path.unlink()
                removed.append(file_path)

        # Remove based on count (keep most recent)
        remaining = [f for f in log_files if f not in removed and f.exists()]
        if len(remaining) > self._max_files:
            for file_path in remaining[: -self._max_files]:
                file_path.unlink()
                removed.append(file_path)

        return removed

    def manage(self) -> dict[str, Any]:
        """Perform rotation and cleanup, return summary."""
        rotated = []
        removed = []

        # Check for files needing rotation
        for file_path in self._log_dir.glob("events-*.jsonl"):
            if self.should_rotate(file_path):
                new_path = self.rotate_file(file_path)
                rotated.append(str(new_path))

        # Cleanup old files
        removed = self.cleanup_old_files()

        return {
            "rotated": rotated,
            "removed": [str(p) for p in removed],
            "remaining": len(list(self._log_dir.glob("*.jsonl*"))),
        }


def get_session_logger(
    command: str | None = None,
    session_id: str | None = None,
) -> SafeSessionLogger:
    """Return a ``SafeSessionLogger`` configured for the current environment."""

    return SafeSessionLogger(
        log_dir=os.getenv("SENGOKU_LOG_DIR"),
        session_id=session_id,
        command=command,
    )


# Provide SafeSessionLogger under the historical name for callers.
SessionLogger = SafeSessionLogger


def ensure_safe_logger(
    logger: Any,
    *,
    where: str | None = None,
) -> SafeSessionLogger:
    """Ensure the provided logger is the hardened implementation.

    Long-running services often receive a logger instance from higher-level
    orchestration. Centralising the guard keeps those call-sites honest and
    avoids sprinkling ad-hoc ``isinstance`` checks across the codebase.
    Returning the validated logger lets callers retain a tidy, fluent style.
    """

    if isinstance(logger, SafeSessionLogger):
        return logger

    location = f" for {where}" if where else ""
    raise RuntimeError(
        "SafeSessionLogger required" + location + "; instantiate via get_session_logger()",
    )


__all__ = [
    "LogRotationManager",
    "ensure_safe_logger",
    "SessionLogger",
    "SessionMetadata",
    "get_session_logger",
]
