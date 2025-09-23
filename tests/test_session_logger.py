"""Tests for enhanced session logging functionality."""

from __future__ import annotations

import json
import time

import pytest

from optipanel.ops.session_logger import (
    LogRotationManager,
    SessionLogger,
    ensure_safe_logger,
    get_session_logger,
)
from optipanel.ops.session_logger_safe import SafeSessionLogger


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def fixed_time(monkeypatch):
    """Fix time for reproducible tests."""
    fixed_timestamp = 1734567890.123  # Arbitrary timestamp
    monkeypatch.setattr(time, "time", lambda: fixed_timestamp)
    return fixed_timestamp


class TestSessionLogger:
    """Tests for SessionLogger class."""

    def test_session_initialization(self, temp_log_dir, fixed_time):
        """Test session logger initialization and ID generation."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test_command")

        assert logger.session_id is not None
        assert logger._command == "test_command"
        assert logger._metadata.start_time == fixed_time
        assert logger._metadata.status == "running"

        # Check that session_start event was emitted
        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]
            kinds = {event["kind"] for event in events}
            assert "session_event" in kinds
            assert any(
                event.get("event_type") == "session_start" and event.get("command") == "test_command"
                for event in events
            )
            assert any(event.get("kind") == "metric" and event.get("metric") == "logger_type" for event in events)

    def test_custom_session_id(self, temp_log_dir):
        """Test using a custom session ID."""
        custom_id = "custom-session-123"
        logger = SessionLogger(log_dir=str(temp_log_dir), session_id=custom_id, command="test")

        assert logger.session_id == custom_id

    def test_emit_with_session_context(self, temp_log_dir):
        """Test that emit includes session context."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        logger.emit("test_event", {"data": "value"})

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]
            assert any(event["kind"] == "session_event" for event in events)
            assert any(event.get("metric") == "logger_type" for event in events if event["kind"] == "metric")

        test_event = next(event for event in events if event["kind"] == "test_event")
        assert test_event["session_id"] == logger.session_id
        assert test_event["command"] == "test"
        assert test_event["data"] == "value"

    def test_operation_context_manager(self, temp_log_dir):
        """Test operation context manager with timing."""
        # Use a simpler approach - just test that the functionality works
        # without mocking time, which will give us a real (small) duration
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        with logger.operation_context("fetch_data", symbol="AAPL"):
            # Small sleep to ensure measurable duration
            time.sleep(0.01)  # 10ms

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            # Find the operation event
            op_events = [e for e in events if e["kind"] == "operation"]
            assert len(op_events) > 0, f"No operation events found. All events: {events}"
            op_event = op_events[0]
            assert op_event["operation"] == "fetch_data"
            assert op_event["details"]["symbol"] == "AAPL"
            # Check duration is at least 10ms (we slept for 10ms)
            assert op_event["duration_ms"] >= 10.0, f"Duration was {op_event['duration_ms']}ms"
            assert op_event["duration_ms"] < 100.0, f"Duration was unexpectedly long: {op_event['duration_ms']}ms"

            # Check metrics were tracked
            assert logger._metadata.metrics["fetch_data"]["count"] == 1
            assert logger._metadata.metrics["fetch_data"]["total_ms"] >= 10.0
            assert logger._metadata.metrics["fetch_data"]["total_ms"] < 100.0

    def test_operation_context_with_error(self, temp_log_dir):
        """Test operation context manager handles errors correctly."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        with pytest.raises(ValueError), logger.operation_context("failing_op", test="data"):
            raise ValueError("Test error")

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            # Should have error event
            error_event = next(e for e in events if e["kind"] == "error")
            assert error_event["error_type"] == "operation_failed"
            assert "failing_op" in error_event["message"]
            assert error_event["exception"]["type"] == "ValueError"

    def test_emit_error(self, temp_log_dir):
        """Test error emission with exception details."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        try:
            raise RuntimeError("Test exception")
        except RuntimeError as e:
            logger.emit_error("test_error", "Something went wrong", details={"context": "testing"}, exception=e)

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            error_event = next(e for e in events if e["kind"] == "error")
            assert error_event["error_type"] == "test_error"
            assert error_event["message"] == "Something went wrong"
            assert error_event["details"]["context"] == "testing"
            assert error_event["exception"]["type"] == "RuntimeError"
            assert "Test exception" in error_event["exception"]["str"]
            assert "traceback" in error_event["exception"]
            assert error_event["error_count"] == 1

    def test_emit_metric(self, temp_log_dir):
        """Test metric emission."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        logger.emit_metric("cache_hit_rate", 0.95, unit="ratio")
        logger.emit_metric("response_time", 123.45, unit="ms")

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            metric_events = [e for e in events if e["kind"] == "metric"]
            assert any(m["metric"] == "logger_type" for m in metric_events)

            user_metrics = [m for m in metric_events if m["metric"] != "logger_type"]
            assert len(user_metrics) == 2

            cache_metric = next(m for m in user_metrics if m["metric"] == "cache_hit_rate")
            assert cache_metric["value"] == 0.95
            assert cache_metric["unit"] == "ratio"

            latency_metric = next(m for m in user_metrics if m["metric"] == "response_time")
            assert latency_metric["value"] == 123.45
            assert latency_metric["unit"] == "ms"

    def test_context_manager_usage(self, temp_log_dir):
        """Test using SessionLogger as a context manager."""
        with SessionLogger(log_dir=str(temp_log_dir), command="test") as logger:
            logger.emit("test", {"data": "value"})

        # Session should be finalized
        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            # Should have session_start, test event, and session_end
            assert any(e.get("event_type") == "session_start" for e in events)
            assert any(e.get("event_type") == "session_end" for e in events)

            end_event = next(e for e in events if e.get("event_type") == "session_end")
            assert end_event["status"] == "completed"
            assert "duration_seconds" in end_event

    def test_context_manager_with_error(self, temp_log_dir):
        """Test context manager handles errors correctly."""
        with pytest.raises(RuntimeError), SessionLogger(log_dir=str(temp_log_dir), command="test"):
            raise RuntimeError("Test error")

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            # Should have error event and session_end with error status
            error_event = next(e for e in events if e["kind"] == "error")
            assert error_event["error_type"] == "session_error"

            end_event = next(e for e in events if e.get("event_type") == "session_end")
            assert end_event["status"] == "error"

    def test_nested_contexts(self, temp_log_dir):
        """Test nested operation contexts."""
        logger = SessionLogger(log_dir=str(temp_log_dir), command="test")

        with logger.operation_context("outer", level=1):
            logger.emit("event1", {"data": "outer"})

            with logger.operation_context("inner", level=2):
                logger.emit("event2", {"data": "inner"})

            logger.emit("event3", {"data": "outer_again"})

        log_files = list(temp_log_dir.glob("events-*.jsonl"))
        with open(log_files[0]) as f:
            events = [json.loads(line) for line in f]

            # Check context tracking
            event1 = next(e for e in events if e.get("data") == "outer")
            assert event1["context"]["operation"] == "outer"
            assert event1["context"]["level"] == 1

            event2 = next(e for e in events if e.get("data") == "inner")
            assert event2["context"]["operation"] == "inner"
            assert event2["context"]["level"] == 2

            event3 = next(e for e in events if e.get("data") == "outer_again")
            assert event3["context"]["operation"] == "outer"
            assert event3["context"]["level"] == 1


class TestLogRotationManager:
    """Tests for LogRotationManager class."""

    def test_should_rotate(self, temp_log_dir):
        """Test rotation detection based on file size."""
        manager = LogRotationManager(str(temp_log_dir), max_size_mb=1, max_age_days=30, max_files=10)  # 1MB limit

        test_file = temp_log_dir / "events-20240101.jsonl"

        # Small file should not rotate
        test_file.write_text("small content")
        assert not manager.should_rotate(test_file)

        # Large file should rotate
        test_file.write_text("x" * (1024 * 1024 + 1))  # > 1MB
        assert manager.should_rotate(test_file)

    def test_rotate_file(self, temp_log_dir, monkeypatch):
        """Test file rotation with timestamp."""
        # Fix time for predictable naming
        monkeypatch.setattr(time, "time", lambda: 1234567890.123)

        manager = LogRotationManager(str(temp_log_dir))

        test_file = temp_log_dir / "events-20240101.jsonl"
        test_file.write_text("test content")

        rotated = manager.rotate_file(test_file)

        # Original file should not exist
        assert not test_file.exists()

        # Rotated file should exist with timestamp
        assert "1234567890123" in str(rotated)

        # Try to read content (might be compressed)
        if rotated.suffix == ".gz":
            import gzip

            with gzip.open(rotated, "rt") as f:
                assert f.read() == "test content"
        else:
            assert rotated.read_text() == "test content"

    def test_cleanup_old_files(self, temp_log_dir, monkeypatch):
        """Test cleanup of old files based on age and count."""
        import os

        # Fix current time
        current_time = 1734567890.0
        monkeypatch.setattr(time, "time", lambda: current_time)

        manager = LogRotationManager(str(temp_log_dir), max_age_days=7, max_files=3)  # 7 days  # Keep only 3 files

        # Create test files with different ages
        old_file = temp_log_dir / "events-20240101.jsonl"
        old_file.write_text("old")

        # Use os.utime to set modification time instead of monkeypatching
        old_time = current_time - (10 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        recent_files = []
        for i in range(5):
            f = temp_log_dir / f"events-2024010{i+2}.jsonl"
            f.write_text(f"recent{i}")
            recent_files.append(f)

        # Old file should be removed based on age
        removed = manager.cleanup_old_files()

        # Verify the old file was removed
        assert not old_file.exists()
        assert isinstance(removed, list)
        assert len(removed) >= 1  # At least the old file

    def test_manage_summary(self, temp_log_dir):
        """Test complete management cycle returns summary."""
        manager = LogRotationManager(str(temp_log_dir), max_size_mb=1, max_age_days=30, max_files=10)

        # Create a large file to rotate
        large_file = temp_log_dir / "events-20240101.jsonl"
        large_file.write_text("x" * (1024 * 1024 + 1))

        # Create a normal file
        normal_file = temp_log_dir / "events-20240102.jsonl"
        normal_file.write_text("normal content")

        result = manager.manage()

        assert "rotated" in result
        assert "removed" in result
        assert "remaining" in result
        assert isinstance(result["rotated"], list)
        assert isinstance(result["removed"], list)
        assert isinstance(result["remaining"], int)


class TestFactoryFunction:
    """Test the get_session_logger factory function."""

    def test_get_session_logger(self, monkeypatch, temp_log_dir):
        """Test factory function creates logger correctly."""
        monkeypatch.setenv("SENGOKU_LOG_DIR", str(temp_log_dir))

        logger = get_session_logger(command="test_command")

        assert isinstance(logger, SafeSessionLogger)
        assert logger._command == "test_command"
        assert logger._root == temp_log_dir

    def test_get_session_logger_with_session_id(self, monkeypatch, temp_log_dir):
        """Test factory with custom session ID."""
        monkeypatch.setenv("SENGOKU_LOG_DIR", str(temp_log_dir))

        logger = get_session_logger(command="test", session_id="custom-123")

        assert logger.session_id == "custom-123"


class TestEnsureSafeLogger:
    """Tests for the ensure_safe_logger guard."""

    def test_accepts_safe_logger(self, monkeypatch, temp_log_dir):
        monkeypatch.setenv("SENGOKU_LOG_DIR", str(temp_log_dir))
        logger = get_session_logger(command="safe_guard")
        try:
            guarded = ensure_safe_logger(logger, where="unit-test")
            assert guarded is logger
        finally:
            logger.finalize()

    def test_rejects_foreign_logger(self):
        with pytest.raises(RuntimeError):
            ensure_safe_logger(object(), where="unit-test")
