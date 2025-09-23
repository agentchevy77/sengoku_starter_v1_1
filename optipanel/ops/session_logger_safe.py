"""Thread-safe enhanced session logging with proper error handling."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import traceback
import uuid
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from optipanel.ops.eventlog import EventLogger


@dataclass
class SessionMetadata:
    """Metadata for a session."""

    session_id: str
    command: str
    start_time: float
    end_time: float | None = None
    duration_seconds: float | None = None
    status: str = "running"
    error_count: int = 0
    event_count: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


class SafeSessionLogger(EventLogger):
    """Thread-safe session logger with proper error handling.

    Fixes critical issues in the original SessionLogger:
    - Thread-safe operations with locks
    - Safe file rotation without data loss
    - Bounded memory usage
    - Proper exception handling
    - Atomic file operations
    """

    # Class-level lock for session ID generation
    _id_lock = threading.Lock()
    _id_counter = 0

    def __init__(
        self,
        log_dir: str | None = None,
        session_id: str | None = None,
        command: str | None = None,
        max_metrics: int = 1000,
        max_context_depth: int = 100,
    ) -> None:
        """Initialize thread-safe session logger.

        Args:
            log_dir: Directory for log files
            session_id: Optional session ID
            command: Command or operation name
            max_metrics: Maximum metrics to track (prevents memory leak)
            max_context_depth: Maximum context stack depth
        """
        super().__init__(log_dir)

        # Thread safety
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        # Generate thread-safe session ID
        self._session_id = session_id or self._generate_safe_session_id()
        self._command = command or "unknown"

        # Limits to prevent memory issues
        self._max_metrics = max_metrics
        self._max_context_depth = max_context_depth

        # Session metadata
        self._metadata = SessionMetadata(
            session_id=self._session_id,
            command=self._command,
            start_time=time.time(),
        )

        # Thread-safe context stack
        self._context_stack: list[dict[str, Any]] = []
        self._finalized = False

        # Safely emit session start
        try:
            self.emit_session_event(
                "session_start",
                {
                    "command": self._command,
                    "pid": os.getpid(),
                    "cwd": self._safe_getcwd(),
                },
            )
        except Exception as e:
            # Log but don't fail initialization
            self._log_internal_error("session_start", e)

        try:
            # Tag newly-created loggers so observability can track adoption.
            self.emit_metric("logger_type", "safe", unit="instance")
        except Exception as e:
            self._log_internal_error("emit_metric(logger_type)", e)

    def _safe_getcwd(self) -> str:
        """Safely get current working directory."""
        try:
            return os.getcwd()
        except (OSError, FileNotFoundError):
            return "<unavailable>"

    def _generate_safe_session_id(self) -> str:
        """Generate guaranteed unique session ID."""
        with SafeSessionLogger._id_lock:
            timestamp = int(time.time() * 1000000)  # Microseconds
            SafeSessionLogger._id_counter += 1
            counter = SafeSessionLogger._id_counter
            unique_part = str(uuid.uuid4())[:8]
            return f"{timestamp}-{counter:04d}-{unique_part}"

    def _log_internal_error(self, operation: str, error: Exception) -> None:
        """Log internal errors without recursion."""
        try:
            # Write to stderr as fallback
            import sys

            sys.stderr.write(f"SessionLogger error in {operation}: {error}\n")
        except Exception:
            pass  # Ultimate fallback - silent failure

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id

    def _safe_json_serialize(self, obj: Any) -> Any:
        """Safely serialize object to JSON-compatible format."""
        try:
            # Try normal serialization first
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            if hasattr(obj, "__dict__"):
                return str(obj)
            elif isinstance(obj, bytes):
                return obj.decode("utf-8", errors="replace")
            elif isinstance(obj, (set | frozenset)):
                return list(obj)
            else:
                return str(obj)

    def emit(self, kind: str, payload: Mapping[str, Any]) -> Path | None:
        """Thread-safe emit with error handling."""
        if self._finalized:
            return None

        with self._lock:
            try:
                # Build enriched payload
                enriched: dict[str, Any] = {
                    "session_id": self._session_id,
                    "command": self._command,
                }

                # Add context if available
                if self._context_stack and len(self._context_stack) <= self._max_context_depth:
                    enriched["context"] = self._context_stack[-1].copy()

                # Safely merge payload
                for key, value in payload.items():
                    enriched[key] = self._safe_json_serialize(value)

                # Update metrics
                self._metadata.event_count += 1

                # Call parent emit with error handling
                return super().emit(kind, enriched)

            except Exception as e:
                self._log_internal_error(f"emit({kind})", e)
                return None

    def emit_session_event(self, event_type: str, details: Mapping[str, Any] | None = None) -> Path | None:
        """Emit a session lifecycle event."""
        try:
            payload = {
                "event_type": event_type,
                "elapsed_seconds": time.time() - self._metadata.start_time,
            }
            if details:
                payload.update(dict(details))

            # Use parent emit to avoid double session_id
            return super().emit("session_event", payload)
        except Exception as e:
            self._log_internal_error("emit_session_event", e)
            return None

    def emit_metric(self, metric_name: str, value: Any, unit: str | None = None) -> Path | None:
        """Emit a metric event."""
        try:
            payload = {
                "metric": metric_name,
                "value": value,
            }
            if unit:
                payload["unit"] = unit

            return self.emit("metric", payload)
        except Exception as e:
            self._log_internal_error("emit_metric", e)
            return None

    def emit_operation(
        self,
        operation: str,
        details: Mapping[str, Any],
        duration_ms: float | None = None,
    ) -> Path | None:
        """Emit operation with bounded metrics tracking."""
        with self._lock:
            try:
                payload = {
                    "operation": operation,
                    "details": dict(details),
                }

                if duration_ms is not None and duration_ms >= 0:
                    payload["duration_ms"] = duration_ms

                    # Bounded metrics tracking
                    if len(self._metadata.metrics) < self._max_metrics:
                        if operation not in self._metadata.metrics:
                            self._metadata.metrics[operation] = {
                                "count": 0,
                                "total_ms": 0,
                                "min_ms": None,
                                "max_ms": None,
                            }

                        metrics = self._metadata.metrics[operation]
                        metrics["count"] += 1
                        metrics["total_ms"] += duration_ms

                        if metrics["min_ms"] is None or duration_ms < metrics["min_ms"]:
                            metrics["min_ms"] = duration_ms
                        if metrics["max_ms"] is None or duration_ms > metrics["max_ms"]:
                            metrics["max_ms"] = duration_ms

                return self.emit("operation", payload)

            except Exception as e:
                self._log_internal_error("emit_operation", e)
                return None

    def emit_error(
        self,
        error_type: str,
        message: str,
        details: Mapping[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> Path | None:
        """Emit error with safe exception handling."""
        with self._lock:
            try:
                self._metadata.error_count += 1

                payload: dict[str, Any] = {
                    "error_type": error_type,
                    "message": str(message)[:1000],  # Limit message length
                    "error_count": self._metadata.error_count,
                }

                if details:
                    payload["details"] = self._safe_json_serialize(dict(details))

                if exception:
                    try:
                        payload["exception"] = {
                            "type": type(exception).__name__,
                            "str": str(exception)[:1000],
                            "traceback": traceback.format_exc()[:5000],  # Limit traceback
                        }
                    except Exception:
                        payload["exception"] = {"type": "unknown", "str": "error serialization failed"}

                return self.emit("error", payload)

            except Exception as e:
                self._log_internal_error("emit_error", e)
                return None

    @contextmanager
    def operation_context(self, operation: str, **kwargs):
        """Thread-safe operation context with proper cleanup."""
        start_time = time.time()
        context = {"operation": operation, **kwargs}

        # Check depth limit
        with self._lock:
            if len(self._context_stack) >= self._max_context_depth:
                self._log_internal_error(
                    "operation_context", Exception(f"Context stack depth exceeded: {self._max_context_depth}")
                )
                yield self
                return

            self._context_stack.append(context)

        exception_occurred = False
        try:
            yield self
        except Exception as e:
            exception_occurred = True
            # Log error but don't fail if logging fails
            with suppress(Exception):
                self.emit_error(
                    "operation_failed",
                    f"Operation '{operation}' failed",
                    details=context,
                    exception=e,
                )
            raise
        finally:
            # Safely pop context
            with self._lock:
                if self._context_stack:
                    with suppress(IndexError):
                        self._context_stack.pop()

            # Emit operation timing only if no exception
            if not exception_occurred:
                with suppress(Exception):
                    duration_ms = (time.time() - start_time) * 1000
                    self.emit_operation(operation, context, duration_ms)

    def finalize(self, status: str = "completed") -> None:
        """Safely finalize session."""
        with self._lock:
            if self._finalized:
                return

            self._finalized = True

            try:
                self._metadata.end_time = time.time()
                self._metadata.duration_seconds = self._metadata.end_time - self._metadata.start_time
                self._metadata.status = status

                # Calculate averages safely
                for _op_name, metrics in self._metadata.metrics.items():
                    if metrics["count"] > 0:
                        metrics["avg_ms"] = metrics["total_ms"] / metrics["count"]

                # Emit session end
                self.emit_session_event(
                    "session_end",
                    {
                        "status": status,
                        "duration_seconds": self._metadata.duration_seconds,
                        "event_count": self._metadata.event_count,
                        "error_count": self._metadata.error_count,
                        "metrics_count": len(self._metadata.metrics),
                    },
                )
            except Exception as e:
                self._log_internal_error("finalize", e)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Safe context manager exit."""
        try:
            if exc_type is not None:
                with suppress(Exception):
                    self.emit_error(
                        "session_error",
                        "Session ended with error",
                        exception=exc_val if isinstance(exc_val, BaseException) else None,
                    )
                self.finalize(status="error")
            else:
                self.finalize(status="completed")
        except Exception as e:
            self._log_internal_error("__exit__", e)

        return False  # Don't suppress original exception


class SafeLogRotationManager:
    """Safe log rotation without data loss."""

    def __init__(
        self,
        log_dir: str,
        max_size_mb: int = 100,
        max_age_days: int = 30,
        max_files: int = 100,
        buffer_size: int = 65536,  # 64KB buffer for file operations
    ) -> None:
        """Initialize safe log rotation manager."""
        self._log_dir = Path(log_dir)
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._max_age_seconds = max_age_days * 24 * 3600
        self._max_files = max_files
        self._buffer_size = buffer_size
        self._lock = threading.Lock()

    def should_rotate(self, file_path: Path) -> bool:
        """Check if rotation needed."""
        try:
            if not file_path.exists():
                return False
            return file_path.stat().st_size > self._max_size_bytes
        except OSError:
            return False

    def rotate_file_safe(self, file_path: Path) -> Path | None:
        """Safely rotate file without data loss."""
        with self._lock:
            try:
                if not file_path.exists():
                    return None

                # Create rotation name
                timestamp = int(time.time() * 1000000)  # Microseconds for uniqueness
                rotated_name = f"{file_path.stem}.{timestamp}{file_path.suffix}"
                rotated_path = file_path.parent / rotated_name

                # Use atomic rename (won't lose data)
                try:
                    file_path.rename(rotated_path)
                except OSError:
                    # Fall back to copy if rename fails (cross-filesystem)
                    shutil.copy2(file_path, rotated_path)
                    file_path.unlink()

                # Try compression in background (don't block)
                try:
                    import gzip

                    compressed_path = Path(f"{rotated_path}.gz")

                    # Stream compression to avoid memory issues
                    with open(rotated_path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                        while True:
                            chunk = f_in.read(self._buffer_size)
                            if not chunk:
                                break
                            f_out.write(chunk)

                    # Only delete original after successful compression
                    rotated_path.unlink()
                    return compressed_path
                except Exception:
                    # Compression failed, keep uncompressed
                    return rotated_path

            except Exception:
                return None

    def cleanup_old_files_safe(self) -> list[str]:
        """Safely cleanup old files."""
        removed = []

        with self._lock:
            try:
                current_time = time.time()

                # Safely collect log files
                log_files = []
                for pattern in ("events-*.jsonl*", "sengoku_*.log*"):
                    with suppress(Exception):
                        log_files.extend(self._log_dir.glob(pattern))

                if not log_files:
                    return removed

                # Safe sort with error handling
                with suppress(Exception):
                    log_files.sort(key=lambda p: p.stat().st_mtime)

                # Remove old files
                for file_path in log_files:
                    try:
                        stat = file_path.stat()
                        age_seconds = current_time - stat.st_mtime

                        if age_seconds > self._max_age_seconds:
                            file_path.unlink()
                            removed.append(str(file_path))
                    except Exception:
                        continue  # Skip files we can't process

                # Remove excess files
                remaining = [f for f in log_files if str(f) not in removed and f.exists()]
                if len(remaining) > self._max_files:
                    for file_path in remaining[: -self._max_files]:
                        with suppress(Exception):
                            file_path.unlink()
                            removed.append(str(file_path))

                return removed

            except Exception:
                return removed


def get_safe_session_logger(
    command: str | None = None,
    session_id: str | None = None,
) -> SafeSessionLogger:
    """Create a safe session logger."""
    return SafeSessionLogger(
        log_dir=os.getenv("SENGOKU_LOG_DIR"),
        session_id=session_id,
        command=command,
    )
