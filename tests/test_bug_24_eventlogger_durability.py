#!/usr/bin/env python3
"""Comprehensive test suite for Bug #24: EventLogger data loss fix.

This test suite validates the critical fix for data loss in EventLogger
where events were lost on application crash due to missing flush().

Bug #24 Details:
- Location: optipanel/ops/eventlog.py (emit method)
- Problem: No flush() after write, data stuck in OS buffer
- Impact: Data loss on application crash
- Fix: Added configurable durability levels with flush/fsync

Test Coverage:
1. Durability level configuration and defaults
2. Data persistence on simulated crashes
3. Performance characteristics of each level
4. Error handling and fallback mechanisms
5. Monitoring capabilities (flush/fsync failure tracking)
6. Backward compatibility
7. Thread safety under concurrent writes
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.ops.eventlog import DurabilityLevel, EventLogger
from optipanel.ops.session_logger_safe import SafeSessionLogger


class TestDurabilityLevels:
    """Test durability level configuration and behavior."""

    def test_durability_enum_values(self):
        """Verify durability levels are properly defined."""
        assert DurabilityLevel.PERFORMANCE.value == 0
        assert DurabilityLevel.STANDARD.value == 1
        assert DurabilityLevel.PARANOID.value == 2

    def test_default_durability_level(self, tmp_path):
        """Verify default durability is STANDARD for safety."""
        logger = EventLogger(log_dir=str(tmp_path))
        assert logger.durability_level == DurabilityLevel.STANDARD

    def test_explicit_durability_level(self, tmp_path):
        """Test setting explicit durability levels."""
        # Test each level
        for level in DurabilityLevel:
            logger = EventLogger(log_dir=str(tmp_path), durability=level)
            assert logger.durability_level == level

    def test_env_var_durability_override(self, tmp_path, monkeypatch):
        """Test environment variable override for durability."""
        # Test valid env values
        for level_name in ["PERFORMANCE", "STANDARD", "PARANOID"]:
            monkeypatch.setenv("SENGOKU_LOG_DURABILITY", level_name)
            logger = EventLogger(log_dir=str(tmp_path))
            assert logger.durability_level == DurabilityLevel[level_name]

    def test_invalid_env_var_defaults_to_standard(self, tmp_path, monkeypatch):
        """Test invalid env var falls back to STANDARD."""
        monkeypatch.setenv("SENGOKU_LOG_DURABILITY", "INVALID")
        logger = EventLogger(log_dir=str(tmp_path))
        assert logger.durability_level == DurabilityLevel.STANDARD


class TestDataPersistence:
    """Test data persistence under various failure scenarios."""

    def test_standard_durability_flush(self, tmp_path):
        """Test STANDARD level calls flush()."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            # Get the actual file handle that will be used
            mock_handle = mock_file.return_value
            logger.emit("test", {"data": "value"})

            # Verify flush was called on the actual handle
            mock_handle.flush.assert_called_once()
            # fsync should NOT be called for STANDARD
            assert not mock_handle.fileno.called

    def test_paranoid_durability_fsync(self, tmp_path):
        """Test PARANOID level calls both flush() and fsync()."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.PARANOID)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file, mock.patch("os.fsync") as mock_fsync:
            mock_handle = mock_file.return_value
            mock_handle.fileno.return_value = 42
            logger.emit("test", {"data": "value"})

            # Verify both flush and fsync were called
            mock_handle.flush.assert_called_once()
            mock_fsync.assert_called_once_with(42)

    def test_performance_no_flush(self, tmp_path):
        """Test PERFORMANCE level skips flush (legacy behavior)."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.PERFORMANCE)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            mock_handle = mock_file.return_value
            logger.emit("test", {"data": "value"})

            # Verify flush was NOT called
            mock_handle.flush.assert_not_called()

    def test_actual_data_persistence(self, tmp_path):
        """Test actual file persistence with different durability levels."""
        # Test each durability level
        for level in [DurabilityLevel.STANDARD, DurabilityLevel.PARANOID]:
            log_dir = tmp_path / f"test_{level.name.lower()}"
            log_dir.mkdir(exist_ok=True)

            logger = EventLogger(log_dir=str(log_dir), durability=level)

            # Write test event
            test_data = {"level": level.name, "value": "persistence_test"}
            path = logger.emit("test_event", test_data)

            # Immediately read file to verify data is persisted
            with open(path) as f:
                lines = f.readlines()
                assert len(lines) == 1

                event = json.loads(lines[0])
                assert event["kind"] == "test_event"
                assert event["level"] == level.name
                assert event["value"] == "persistence_test"

    def test_crash_simulation_subprocess(self, tmp_path):
        """Simulate crash scenario using subprocess to test data persistence."""
        test_script = tmp_path / "crash_test.py"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create test script that writes and crashes
        script_content = f"""
import sys
import os
sys.path.insert(0, "{Path(__file__).parent.parent}")
from optipanel.ops.eventlog import EventLogger, DurabilityLevel

logger = EventLogger(log_dir="{log_dir}", durability=DurabilityLevel.STANDARD)
logger.emit("before_crash", {{"test": "data"}})
# Simulate crash without proper shutdown
os._exit(1)
"""
        test_script.write_text(script_content)

        # Run script
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True)
        assert result.returncode == 1  # Verify it crashed

        # Check data was persisted despite crash
        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            assert len(lines) == 1
            event = json.loads(lines[0])
            assert event["kind"] == "before_crash"
            assert event["test"] == "data"


class TestErrorHandling:
    """Test error handling and fallback mechanisms."""

    def test_flush_failure_handling(self, tmp_path):
        """Test graceful handling of flush failures."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            mock_handle = mock_file.return_value
            # Simulate flush failure
            mock_handle.flush.side_effect = OSError("Flush failed")

            # Should not raise exception
            path = logger.emit("test", {"data": "value"})
            assert path is not None

            # Check failure was tracked
            assert logger.flush_failures == 1

    def test_fsync_failure_handling(self, tmp_path):
        """Test graceful handling of fsync failures."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.PARANOID)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file, mock.patch("os.fsync") as mock_fsync:
            mock_handle = mock_file.return_value
            mock_handle.fileno.return_value = 42
            mock_fsync.side_effect = OSError("Fsync failed")

            # Should not raise exception
            path = logger.emit("test", {"data": "value"})
            assert path is not None

            # Check failure was tracked
            assert logger.fsync_failures == 1

    def test_write_failure_fallback_to_stderr(self, tmp_path, capsys):
        """Test fallback to stderr when file write fails."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        with mock.patch("builtins.open") as mock_open:
            # Simulate file write failure
            mock_open.side_effect = OSError("Cannot write to file")

            # Should fallback to stderr
            logger.emit("test", {"data": "fallback_test"})

            # Check stderr output
            captured = capsys.readouterr()
            assert "FALLBACK_LOG" in captured.err
            assert "fallback_test" in captured.err

    def test_monitoring_failure_counts(self, tmp_path):
        """Test failure counting for monitoring."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.PARANOID)

        # Initial counts should be zero
        assert logger.flush_failures == 0
        assert logger.fsync_failures == 0

        with mock.patch("builtins.open", mock.mock_open()) as mock_file, mock.patch("os.fsync") as mock_fsync:
            mock_handle = mock_file.return_value
            mock_handle.fileno.return_value = 42

            # Simulate multiple failures
            mock_handle.flush.side_effect = OSError("Flush failed")
            mock_fsync.side_effect = OSError("Fsync failed")

            for _ in range(3):
                logger.emit("test", {"data": "value"})

            assert logger.flush_failures == 3
            # fsync not called because flush failed
            assert logger.fsync_failures == 0


class TestPerformance:
    """Test performance characteristics of durability levels."""

    def test_performance_comparison(self, tmp_path):
        """Compare performance of different durability levels."""
        results = {}
        num_events = 100

        for level in DurabilityLevel:
            log_dir = tmp_path / f"perf_{level.name.lower()}"
            log_dir.mkdir()

            logger = EventLogger(log_dir=str(log_dir), durability=level)

            start_time = time.time()
            for i in range(num_events):
                logger.emit("perf_test", {"index": i, "data": "x" * 100})
            elapsed = time.time() - start_time

            results[level.name] = elapsed

        # PERFORMANCE should be fastest (no flush)
        assert results["PERFORMANCE"] <= results["STANDARD"]
        # PARANOID should be slowest (flush + fsync)
        assert results["STANDARD"] <= results["PARANOID"]

        # Verify reasonable performance (not hanging)
        for level_name, elapsed in results.items():
            assert elapsed < 5.0, f"{level_name} took too long: {elapsed}s"

    def test_concurrent_writes_thread_safety(self, tmp_path):
        """Test thread safety with concurrent writes."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        num_threads = 10
        events_per_thread = 50
        errors = []

        def write_events(thread_id):
            try:
                for i in range(events_per_thread):
                    logger.emit("concurrent", {"thread": thread_id, "index": i})
            except Exception as e:
                errors.append((thread_id, e))

        threads = []
        for tid in range(num_threads):
            t = threading.Thread(target=write_events, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # Verify all events were written
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            assert len(lines) == num_threads * events_per_thread

            # Verify data integrity
            events = [json.loads(line) for line in lines]
            thread_counts = {}
            for event in events:
                tid = event["thread"]
                thread_counts[tid] = thread_counts.get(tid, 0) + 1

            # Each thread should have written exactly events_per_thread events
            for tid in range(num_threads):
                assert thread_counts[tid] == events_per_thread


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_eventlogger_without_durability_param(self, tmp_path):
        """Test EventLogger works without durability parameter (legacy usage)."""
        # Old code that doesn't pass durability should still work
        logger = EventLogger(log_dir=str(tmp_path))
        path = logger.emit("test", {"data": "legacy"})

        # Should use STANDARD by default
        assert logger.durability_level == DurabilityLevel.STANDARD

        # Verify event was written
        with open(path) as f:
            event = json.loads(f.readline())
            assert event["kind"] == "test"
            assert event["data"] == "legacy"

    def test_safe_session_logger_compatibility(self, tmp_path):
        """Test SafeSessionLogger works with new durability parameter."""
        # Without durability (should default to STANDARD)
        logger1 = SafeSessionLogger(log_dir=str(tmp_path))
        assert logger1.durability_level == DurabilityLevel.STANDARD

        # With explicit durability
        logger2 = SafeSessionLogger(log_dir=str(tmp_path), durability=DurabilityLevel.PARANOID)
        assert logger2.durability_level == DurabilityLevel.PARANOID

        # Test emit works
        logger2.emit("session", {"test": "data"})

        # Verify session was properly initialized
        assert logger2.session_id is not None
        assert logger2._metadata.event_count == 2  # start + emit


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_payload(self, tmp_path):
        """Test handling of very large payloads."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        # Create large payload (1MB of data)
        large_data = "x" * (1024 * 1024)
        path = logger.emit("large", {"data": large_data})

        # Verify it was written correctly
        with open(path) as f:
            event = json.loads(f.readline())
            assert event["kind"] == "large"
            assert len(event["data"]) == 1024 * 1024

    def test_special_characters_in_payload(self, tmp_path):
        """Test handling of special characters."""
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        special_data = {
            "unicode": "🔥 Test 你好 мир",
            "newlines": "line1\nline2\nline3",
            "tabs": "col1\tcol2\tcol3",
            "quotes": 'He said "hello"',
            "backslash": "path\\to\\file",
            "null_byte": "before\x00after",
        }

        path = logger.emit("special", special_data)

        # Verify all special characters preserved
        with open(path) as f:
            event = json.loads(f.readline())
            assert event["unicode"] == special_data["unicode"]
            assert event["newlines"] == special_data["newlines"]
            assert event["tabs"] == special_data["tabs"]
            assert event["quotes"] == special_data["quotes"]
            assert event["backslash"] == special_data["backslash"]

    def test_rapid_date_rollover(self, tmp_path):
        """Test handling of date rollover during logging."""
        # Test that logger can handle writing to different date files
        logger = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        # Manually create file for day 1
        day1_file = tmp_path / "events-20240101.jsonl"
        day1_file.touch()

        # Manually create file for day 2
        day2_file = tmp_path / "events-20240102.jsonl"
        day2_file.touch()

        # Write to current day file (whatever today is)
        logger.emit("test", {"data": "today"})

        # Should have at least 3 files (2 manual + 1 from emit)
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) >= 3


class TestIntegration:
    """Integration tests with real-world scenarios."""

    def test_full_session_logging_workflow(self, tmp_path):
        """Test complete session logging workflow with durability."""
        with SafeSessionLogger(
            log_dir=str(tmp_path), command="test_command", durability=DurabilityLevel.PARANOID
        ) as logger:
            # Simulate session activities
            logger.emit_metric("startup_time", 1.23, "seconds")

            with logger.operation_context("data_processing"):
                logger.emit("processing", {"records": 1000})
                time.sleep(0.01)  # Simulate work

            logger.emit_error("validation", "Invalid record", {"record_id": 42})

        # Verify all events persisted
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            events = [json.loads(line) for line in lines]

            # Should have multiple event types
            event_kinds = {e["kind"] for e in events}
            assert "session_event" in event_kinds
            assert "metric" in event_kinds
            assert "processing" in event_kinds
            assert "operation" in event_kinds
            assert "error" in event_kinds

    def test_crash_recovery_scenario(self, tmp_path):
        """Test recovery after simulated crash with partial writes."""
        # Test that logger can continue writing after a crash left incomplete data
        logger1 = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)

        # Write some complete events
        path1 = logger1.emit("complete1", {"data": "first"})
        path2 = logger1.emit("complete2", {"data": "second"})

        # Simulate partial write (as if crashed mid-write) by appending corrupt data
        with open(path1, "a") as f:
            f.write('{"ts": 1234567890, "kind": "partial", "data": "incomp')
            # No closing brace, no newline - simulates crash during write

        # New logger instance (simulating restart after crash)
        logger2 = EventLogger(log_dir=str(tmp_path), durability=DurabilityLevel.STANDARD)
        path3 = logger2.emit("after_crash", {"data": "recovered"})

        # Read and verify file integrity
        with open(path1) as f:
            lines = f.readlines()

            # First two lines should be valid JSON
            event1 = json.loads(lines[0])
            assert event1["kind"] == "complete1"

            event2 = json.loads(lines[1])
            assert event2["kind"] == "complete2"

            # Third line is corrupt (partial write) - just verify it exists
            assert len(lines) >= 3
            assert "incomp" in lines[2]

            # Fourth line should be valid (after recovery)
            if len(lines) > 3:
                event4 = json.loads(lines[3])
                assert event4["kind"] == "after_crash"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
