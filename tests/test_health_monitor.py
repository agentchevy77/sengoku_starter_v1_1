"""Tests for production health monitoring system."""

import json
import time

import pytest

from optipanel.monitoring import health_monitor
from optipanel.monitoring.health_monitor import (
    HealthMonitor,
    MonitoredContext,
    get_monitor,
    monitored_operation,
)


@pytest.fixture(autouse=True)
def reset_global_monitor():
    """Ensure each test gets a clean HealthMonitor singleton."""

    with health_monitor._monitor_lock:
        original = health_monitor._monitor
        health_monitor._monitor = None

    try:
        yield
    finally:
        with health_monitor._monitor_lock:
            health_monitor._monitor = original


class TestHealthMonitor:
    def test_record_error(self):
        monitor = HealthMonitor(max_errors=10)

        # Record some errors
        try:
            raise ValueError("Test error")
        except ValueError as e:
            monitor.record_error(e, {"test": "data"})

        assert monitor.total_errors == 1
        assert len(monitor.errors) == 1
        assert monitor.errors[0].error_type == "ValueError"

    def test_error_buffer_limit(self):
        monitor = HealthMonitor(max_errors=5)

        # Record more errors than limit
        for i in range(10):
            try:
                raise ValueError(f"Error {i}")
            except ValueError as e:
                monitor.record_error(e)

        # Should only keep last 5
        assert len(monitor.errors) == 5
        assert monitor.total_errors == 10
        assert "Error 9" in monitor.errors[-1].error_msg

    def test_record_metric(self):
        monitor = HealthMonitor()

        monitor.record_metric("test_op", 100.5, True, {"key": "value"})

        assert monitor.total_operations == 1
        assert len(monitor.metrics) == 1
        assert monitor.metrics[0].operation == "test_op"
        assert monitor.metrics[0].duration_ms == 100.5

    def test_health_status(self):
        monitor = HealthMonitor()

        # Record some activity
        monitor.record_metric("op1", 50.0, True)
        monitor.record_metric("op2", 150.0, False)

        try:
            raise RuntimeError("Test error")
        except RuntimeError as e:
            monitor.record_error(e)

        status = monitor.get_health_status()

        assert status["total_errors"] == 1
        assert status["total_operations"] == 2
        assert "RuntimeError" in status["error_types"]
        assert status["success_rate_percent"] == 50.0

    def test_alert_threshold(self):
        monitor = HealthMonitor(alert_threshold=3, alert_window_seconds=1.0)

        # Trigger alert by recording many errors quickly
        for i in range(5):
            try:
                raise ValueError(f"Error {i}")
            except ValueError as e:
                monitor.record_error(e)

        assert monitor.alerts_sent > 0

    def test_export_data(self, tmp_path):
        monitor = HealthMonitor()

        # Add some data
        monitor.record_metric("fetch", 100.0, True)
        try:
            raise ValueError("Export test")
        except ValueError as e:
            monitor.record_error(e)

        # Export
        export_file = tmp_path / "health.json"
        monitor.export_data(export_file)

        # Verify export
        assert export_file.exists()
        with export_file.open() as f:
            data = json.load(f)
            assert "health" in data
            assert "recent_errors" in data
            assert "performance_summary" in data


class TestMonitoredOperation:
    def test_successful_operation(self):
        # Use the global monitor via get_monitor
        from optipanel.monitoring import health_monitor

        monitor = HealthMonitor()
        health_monitor._monitor = monitor  # Set the global instance

        @monitored_operation("test_func")
        def successful_func(x):
            time.sleep(0.01)  # Simulate work
            return x * 2

        result = successful_func(5)

        assert result == 10
        assert monitor.total_operations == 1
        assert monitor.metrics[0].success is True
        assert monitor.metrics[0].duration_ms > 10  # At least 10ms

    def test_failed_operation(self):
        from optipanel.monitoring import health_monitor

        monitor = HealthMonitor()
        health_monitor._monitor = monitor

        @monitored_operation("failing_func")
        def failing_func():
            raise ValueError("Intentional failure")

        with pytest.raises(ValueError):
            failing_func()

        assert monitor.total_errors == 1
        assert monitor.total_operations == 1
        assert monitor.errors[0].error_type == "ValueError"
        assert monitor.metrics[0].success is False


class TestMonitoredContext:
    def test_successful_context(self):
        from optipanel.monitoring import health_monitor

        monitor = HealthMonitor()
        health_monitor._monitor = monitor

        with MonitoredContext("test_block") as ctx:
            ctx.add_metadata({"user": "test"})
            time.sleep(0.01)

        assert monitor.total_operations == 1
        assert monitor.metrics[0].success is True
        assert monitor.metrics[0].metadata["user"] == "test"

    def test_failed_context(self):
        from optipanel.monitoring import health_monitor

        monitor = HealthMonitor()
        health_monitor._monitor = monitor

        try:
            with MonitoredContext("failing_block"):
                raise RuntimeError("Context failure")
        except RuntimeError:
            pass

        assert monitor.total_errors == 1
        assert monitor.total_operations == 1
        assert monitor.errors[0].error_type == "RuntimeError"
        assert monitor.metrics[0].success is False

    def test_context_metadata(self):
        from optipanel.monitoring import health_monitor

        monitor = HealthMonitor()
        health_monitor._monitor = monitor

        with MonitoredContext("metadata_test") as ctx:
            ctx.add_metadata({"step": 1})
            ctx.add_metadata({"step": 2, "extra": "data"})

        metadata = monitor.metrics[0].metadata
        assert metadata["step"] == 2
        assert metadata["extra"] == "data"


class TestGlobalMonitor:
    def test_singleton_instance(self):
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2  # Same instance

    def test_thread_safety(self):
        """Test that monitor is thread-safe."""
        import threading

        monitor = HealthMonitor()

        def record_many():
            try:
                for i in range(100):
                    monitor.record_metric(f"op_{i}", i, True)
                    if i % 10 == 0:
                        raise ValueError(f"Error {i}")
            except ValueError as e:
                monitor.record_error(e)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=record_many)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have recorded without crashes
        assert monitor.total_operations > 0
        assert monitor.total_errors > 0
