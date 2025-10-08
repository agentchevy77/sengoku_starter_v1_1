"""Production health monitoring system for Sengoku.

This module provides comprehensive monitoring for production deployments,
tracking errors, performance metrics, and system health.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from contextlib import suppress

logger = logging.getLogger(__name__)


_ALERT_LOG_ENV_VAR = "SENGOKU_ALERT_LOG_PATH"


def _ensure_private_directory(directory: Path) -> Path:
    """Create *directory* with restrictive permissions if it does not exist."""

    directory.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        # chmod isn't reliable on all platforms (e.g., Windows); best effort only
        directory.chmod(0o700)
    return directory


def _resolve_alert_log_path() -> Path:
    """Return a secure location for the alert log, favoring user-specific storage."""

    env_path = os.getenv(_ALERT_LOG_ENV_VAR)
    if env_path:
        path = Path(env_path).expanduser()
        _ensure_private_directory(path.parent)
        return path

    base_state = os.getenv("XDG_STATE_HOME")
    preferred_base = Path(base_state) if base_state else Path.home() / ".local" / "state"

    try:
        alerts_dir = _ensure_private_directory(preferred_base / "sengoku")
        return alerts_dir / "alerts.log"
    except PermissionError:
        # Fall back to repository-local state directory when home is not writable
        fallback_dir = _ensure_private_directory(Path.cwd() / ".sengoku_state")
        return fallback_dir / "alerts.log"


def _open_secure_append(path: Path):
    """Open *path* for append using O_NOFOLLOW via Path.open's custom opener."""

    base_flags = os.O_APPEND | os.O_WRONLY | os.O_CREAT
    base_flags |= getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        base_flags |= os.O_NOFOLLOW

    def _secure_opener(file_path: str, flags: int) -> int:
        combined_flags = flags | base_flags
        return os.open(file_path, combined_flags, 0o600)

    return path.open("a", encoding="utf-8", opener=_secure_opener)


@dataclass
class ErrorEvent:
    """Represents a captured error event."""

    timestamp: float
    error_type: str
    error_msg: str
    stack_trace: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    """Represents a performance measurement."""

    timestamp: float
    operation: str
    duration_ms: float
    success: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """Production health monitoring with error tracking and alerting.

    Features:
    - Thread-safe error collection
    - Performance metric tracking
    - Automatic alerting on thresholds
    - JSON export for analysis
    - Circular buffers to prevent memory issues
    """

    def __init__(
        self,
        max_errors: int = 1000,
        max_metrics: int = 10000,
        alert_threshold: int = 10,
        alert_window_seconds: float = 60.0,
    ):
        """Initialize health monitor.

        Args:
            max_errors: Maximum errors to retain in memory
            max_metrics: Maximum metrics to retain
            alert_threshold: Error count to trigger alert
            alert_window_seconds: Time window for error rate calculation
        """
        self._lock = threading.RLock()
        self.errors = deque(maxlen=max_errors)
        self.metrics = deque(maxlen=max_metrics)
        self.alert_threshold = alert_threshold
        self.alert_window = alert_window_seconds
        self.start_time = time.time()
        self.total_errors = 0
        self.total_operations = 0
        self.alerts_sent = 0

    def record_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record an error event.

        Args:
            error: The exception that occurred
            context: Additional context about the error
        """
        with self._lock:
            self.total_errors += 1
            event = ErrorEvent(
                timestamp=time.time(),
                error_type=type(error).__name__,
                error_msg=str(error),
                stack_trace=traceback.format_exc(),
                context=context or {},
            )
            self.errors.append(event)

            # Check if we need to send an alert
            self._check_alert_threshold()

    def record_metric(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a performance metric.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            metadata: Additional metadata
        """
        with self._lock:
            self.total_operations += 1
            metric = PerformanceMetric(
                timestamp=time.time(),
                operation=operation,
                duration_ms=duration_ms,
                success=success,
                metadata=metadata or {},
            )
            self.metrics.append(metric)

    def _check_alert_threshold(self) -> None:
        """Check if error rate exceeds threshold and send alert.

        FIX for Bug #49: Use >= instead of > to include errors at exact cutoff boundary.
        Time windows are inclusive: "last N seconds" means [now-N, now].
        """
        now = time.time()
        cutoff = now - self.alert_window

        # FIX Bug #49: Changed > to >= to include boundary errors
        recent_errors = sum(1 for e in self.errors if e.timestamp >= cutoff)

        if recent_errors >= self.alert_threshold:
            self.alerts_sent += 1
            self._send_alert(recent_errors)

    def _send_alert(self, error_count: int) -> None:
        """Send alert about high error rate.

        Args:
            error_count: Number of errors in window
        """
        logger.critical(
            "HIGH ERROR RATE ALERT: %d errors in last %d seconds",
            error_count,
            int(self.alert_window),
        )

        # In production, this would send to PagerDuty, Slack, etc.
        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "type": "high_error_rate",
            "error_count": error_count,
            "window_seconds": self.alert_window,
            "threshold": self.alert_threshold,
        }
        alert_line = json.dumps(alert_data) + "\n"

        alert_file = _resolve_alert_log_path()

        try:
            with _open_secure_append(alert_file) as f:
                f.write(alert_line)
        except FileNotFoundError:
            # Parent directory was removed after resolution; recreate and retry once.
            try:
                _ensure_private_directory(alert_file.parent)
                with _open_secure_append(alert_file) as f:
                    f.write(alert_line)
            except Exception:
                logger.exception("Failed to write alert to file after recreating directory")
        except OSError:
            # Includes potential ELOOP from O_NOFOLLOW when a symlink attack is detected.
            logger.exception("Failed to write alert to file due to secure-open failure")
        except Exception:
            logger.exception("Failed to write alert to file")

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status summary.

        Returns:
            Dictionary with health metrics
        """
        with self._lock:
            now = time.time()
            uptime = now - self.start_time

            # Calculate error rate
            recent_cutoff = now - 300  # Last 5 minutes
            # FIX Bug #49: Changed > to >= to include boundary errors
            recent_errors = sum(1 for e in self.errors if e.timestamp >= recent_cutoff)
            error_rate = recent_errors / 5.0  # Per minute

            # Calculate performance stats
            # FIX Bug #49: Changed > to >= to include boundary metrics
            recent_metrics = [m for m in self.metrics if m.timestamp >= recent_cutoff]
            if recent_metrics:
                avg_duration = sum(m.duration_ms for m in recent_metrics) / len(recent_metrics)
                success_rate = sum(1 for m in recent_metrics if m.success) / len(recent_metrics) * 100
            else:
                avg_duration = 0.0
                success_rate = 100.0

            # Get error breakdown
            error_types = {}
            for error in self.errors:
                error_types[error.error_type] = error_types.get(error.error_type, 0) + 1

            return {
                "status": "healthy" if error_rate < 1.0 else "degraded" if error_rate < 5.0 else "unhealthy",
                "uptime_seconds": uptime,
                "total_errors": self.total_errors,
                "total_operations": self.total_operations,
                "error_rate_per_minute": error_rate,
                "avg_operation_ms": avg_duration,
                "success_rate_percent": success_rate,
                "alerts_sent": self.alerts_sent,
                "error_types": error_types,
                "recent_errors": recent_errors,
            }

    def export_data(self, output_path: Path) -> None:
        """Export monitoring data to JSON file.

        Args:
            output_path: Path to write JSON export
        """
        with self._lock:
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "health": self.get_health_status(),
                "recent_errors": [
                    {
                        "timestamp": e.timestamp,
                        "type": e.error_type,
                        "message": e.error_msg,
                        "context": e.context,
                    }
                    for e in list(self.errors)[-10:]  # Last 10 errors
                ],
                "performance_summary": self._get_performance_summary(),
            }

            try:
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, default=str)
                logger.info("Health data exported to %s", output_path)
            except Exception:
                logger.exception("Failed to export health data")

    def _get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary by operation."""
        op_stats: dict[str, dict[str, Any]] = {}

        for metric in self.metrics:
            op = metric.operation
            if op not in op_stats:
                op_stats[op] = {
                    "count": 0,
                    "total_ms": 0.0,
                    "failures": 0,
                    "min_ms": float("inf"),
                    "max_ms": 0.0,
                }

            stats = op_stats[op]
            stats["count"] += 1
            stats["total_ms"] += metric.duration_ms
            stats["min_ms"] = min(stats["min_ms"], metric.duration_ms)
            stats["max_ms"] = max(stats["max_ms"], metric.duration_ms)
            if not metric.success:
                stats["failures"] += 1

        # Calculate averages
        for stats in op_stats.values():
            if stats["count"] > 0:
                stats["avg_ms"] = stats["total_ms"] / stats["count"]
                stats["success_rate"] = (stats["count"] - stats["failures"]) / stats["count"] * 100
            else:
                stats["avg_ms"] = 0.0
                stats["success_rate"] = 0.0

        return op_stats


# Global singleton instance
_monitor: HealthMonitor | None = None
_monitor_lock = threading.Lock()


def get_monitor() -> HealthMonitor:
    """Get the global health monitor instance."""
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = HealthMonitor()
    return _monitor


def monitored_operation(operation_name: str):
    """Decorator to monitor function execution.

    Args:
        operation_name: Name for this operation in metrics

    Example:
        @monitored_operation("fetch_market_data")
        def fetch_data(symbols):
            # ... implementation
            return data
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_monitor()
            start = time.perf_counter()
            success = False

            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as exc:
                monitor.record_error(exc, {"operation": operation_name, "args": str(args)[:200]})
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                monitor.record_metric(operation_name, duration_ms, success)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# Context manager for monitoring code blocks
class MonitoredContext:
    """Context manager for monitoring code blocks.

    Example:
        with MonitoredContext("database_query") as ctx:
            # ... perform operation
            ctx.add_metadata({"query": "SELECT * FROM users"})
    """

    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = 0.0
        self.metadata: dict[str, Any] = {}
        self.monitor = get_monitor()

    def add_metadata(self, data: dict[str, Any]) -> None:
        """Add metadata to this operation."""
        self.metadata.update(data)

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        success = exc_type is None

        if exc_val is not None:
            self.monitor.record_error(exc_val, {"operation": self.operation, **self.metadata})

        self.monitor.record_metric(self.operation, duration_ms, success, self.metadata)

        # Don't suppress the exception
        return False
