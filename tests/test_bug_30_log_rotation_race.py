"""Test for Bug #30: Multi-process race condition in log rotation.

This test verifies that the ProcessSafeLock mechanism prevents race conditions
when multiple processes attempt to rotate the same log file simultaneously.
"""

import multiprocessing
import os
import tempfile
import time
from pathlib import Path

import pytest

from optipanel.ops.session_logger_safe import ProcessSafeLock, SafeLogRotationManager


class TestProcessSafeLock:
    """Test the ProcessSafeLock implementation."""

    def test_single_process_lock_acquire_release(self):
        """Test basic lock acquire and release in a single process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            lock = ProcessSafeLock(lock_file, timeout=1.0)

            # Should acquire lock successfully
            assert lock.acquire()

            # Lock file should exist and contain PID
            assert lock_file.exists()
            with open(lock_file) as f:
                content = f.read().strip()
                assert content == str(os.getpid())

            # Release lock
            lock.release()

            # Should be able to acquire again
            assert lock.acquire()
            lock.release()

    def test_lock_timeout(self):
        """Test that lock acquisition times out properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            lock1 = ProcessSafeLock(lock_file, timeout=0.1)  # Short timeout
            lock2 = ProcessSafeLock(lock_file, timeout=0.1)

            # First lock should succeed
            assert lock1.acquire()

            # Second lock should timeout
            start = time.time()
            assert not lock2.acquire()
            elapsed = time.time() - start

            # Should have waited approximately the timeout period
            assert 0.08 < elapsed < 0.3  # Allow some tolerance

            lock1.release()

    def test_context_manager(self):
        """Test lock as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"

            # Should work as context manager
            with ProcessSafeLock(lock_file, timeout=1.0) as lock:
                assert lock_file.exists()

            # Lock should be released after context
            # New lock should succeed
            with ProcessSafeLock(lock_file, timeout=1.0) as lock:
                assert lock_file.exists()

    def test_context_manager_timeout_raises(self):
        """Test that context manager raises on timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            lock1 = ProcessSafeLock(lock_file, timeout=0.1)

            # Acquire first lock
            assert lock1.acquire()

            # Second lock should raise TimeoutError in context manager
            with pytest.raises(TimeoutError), ProcessSafeLock(lock_file, timeout=0.1):
                pass

            lock1.release()


class TestSafeLogRotationManager:
    """Test the SafeLogRotationManager with process-safe locking."""

    def test_rotation_creates_lock_directory(self):
        """Test that lock directory is created on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SafeLogRotationManager(tmpdir)
            lock_dir = Path(tmpdir) / ".locks"
            assert lock_dir.exists()
            assert lock_dir.is_dir()

    def test_single_process_rotation(self):
        """Test basic log rotation in a single process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SafeLogRotationManager(tmpdir, max_size_mb=1, buffer_size=8192)  # 1MB max size

            # Create a log file that exceeds size limit
            log_file = Path(tmpdir) / "events-20240101.jsonl"
            content = "x" * (2 * 1024 * 1024)  # 2MB
            log_file.write_text(content)

            # Should need rotation
            assert manager.should_rotate(log_file)

            # Rotate the file
            rotated = manager.rotate_file_safe(log_file)
            assert rotated is not None

            # Original file should not exist
            assert not log_file.exists()

            # Rotated file should exist (either compressed or not)
            assert rotated.exists() or Path(str(rotated).replace(".gz", "")).exists()

    def test_concurrent_rotation_safety(self):
        """Test that concurrent rotation attempts are handled safely."""

        def rotate_worker(tmpdir: str, worker_id: int, results: dict):
            """Worker function for rotation test."""
            try:
                manager = SafeLogRotationManager(tmpdir, max_size_mb=1, lock_timeout=5.0)

                log_file = Path(tmpdir) / "events-test.jsonl"

                # Try to rotate the file
                rotated = manager.rotate_file_safe(log_file)

                # Record result
                results[worker_id] = {
                    "success": rotated is not None,
                    "rotated_path": str(rotated) if rotated else None,
                    "pid": os.getpid(),
                }
            except Exception as e:
                results[worker_id] = {"success": False, "error": str(e), "pid": os.getpid()}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large log file
            log_file = Path(tmpdir) / "events-test.jsonl"
            content = "x" * (2 * 1024 * 1024)  # 2MB
            log_file.write_text(content)

            # Use multiprocessing.Manager for shared results
            with multiprocessing.Manager() as manager:
                results = manager.dict()
                processes = []

                # Start multiple processes trying to rotate the same file
                for i in range(3):
                    p = multiprocessing.Process(target=rotate_worker, args=(tmpdir, i, results))
                    p.start()
                    processes.append(p)

                # Wait for all processes to complete
                for p in processes:
                    p.join(timeout=10)

                # Convert to regular dict for analysis
                results_dict = dict(results)

                # Only one process should successfully rotate
                successful = [r for r in results_dict.values() if r["success"]]

                # Due to double-checking in the code, it's possible that all processes
                # report no success if the first one rotates before others acquire lock
                # This is the correct behavior - no duplicate rotations
                assert len(successful) <= 1, "Multiple processes rotated the same file!"

                # Original file should not exist
                assert not log_file.exists()

                # At least one rotated file should exist in the directory
                rotated_files = list(Path(tmpdir).glob("events-test.*.jsonl*"))
                assert len(rotated_files) >= 1, "No rotated files found"

    def test_cleanup_with_lock(self):
        """Test that cleanup operations use proper locking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SafeLogRotationManager(tmpdir, max_age_days=0, max_files=2)  # Delete immediately

            # Create some old log files
            for i in range(5):
                log_file = Path(tmpdir) / f"events-2024010{i}.jsonl"
                log_file.write_text(f"log content {i}")
                # Make them old
                os.utime(log_file, (0, 0))

            # Run cleanup
            removed = manager.cleanup_old_files_safe()

            # Should have removed files
            assert len(removed) > 0

            # Should have lock directory
            lock_dir = Path(tmpdir) / ".locks"
            assert lock_dir.exists()

    def test_lock_cleanup(self):
        """Test that stale lock files are cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SafeLogRotationManager(tmpdir)
            lock_dir = Path(tmpdir) / ".locks"

            # Create some stale lock files
            for i in range(3):
                lock_file = lock_dir / f"stale{i}.lock"
                lock_file.touch()
                # Make them old (2 hours)
                old_time = time.time() - 7200
                os.utime(lock_file, (old_time, old_time))

            # Create a recent lock file
            recent_lock = lock_dir / "recent.lock"
            recent_lock.touch()

            # Run cleanup
            manager._cleanup_old_locks()

            # Stale locks should be removed
            for i in range(3):
                assert not (lock_dir / f"stale{i}.lock").exists()

            # Recent lock should remain
            assert recent_lock.exists()


def test_stress_concurrent_operations():
    """Stress test with multiple concurrent rotation and cleanup operations."""

    def worker(tmpdir: str, worker_id: int, operation: str):
        """Worker for stress test."""
        manager = SafeLogRotationManager(tmpdir, max_size_mb=1, max_files=10, lock_timeout=10.0)

        for i in range(5):
            if operation == "rotate":
                # Try to rotate files
                log_file = Path(tmpdir) / f"events-{worker_id}-{i}.jsonl"
                if not log_file.exists():
                    log_file.write_text("x" * (2 * 1024 * 1024))
                manager.rotate_file_safe(log_file)
            elif operation == "cleanup":
                # Try to cleanup files
                manager.cleanup_old_files_safe()

            # Small delay to increase chance of contention
            time.sleep(0.01)

    with tempfile.TemporaryDirectory() as tmpdir:
        processes = []

        # Start rotation workers
        for i in range(3):
            p = multiprocessing.Process(target=worker, args=(tmpdir, i, "rotate"))
            p.start()
            processes.append(p)

        # Start cleanup workers
        for i in range(2):
            p = multiprocessing.Process(target=worker, args=(tmpdir, i + 10, "cleanup"))
            p.start()
            processes.append(p)

        # Wait for all processes with timeout
        for p in processes:
            p.join(timeout=30)
            if p.is_alive():
                p.terminate()
                p.join()

        # Verify no deadlocks occurred (all processes completed)
        for p in processes:
            assert p.exitcode == 0, "Process failed or was terminated"

        # Verify lock directory exists
        lock_dir = Path(tmpdir) / ".locks"
        assert lock_dir.exists()

        # No lock files should remain (all were released)
        remaining_locks = list(lock_dir.glob("*.lock"))
        assert len(remaining_locks) == 0, f"Lock files not cleaned up: {remaining_locks}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
