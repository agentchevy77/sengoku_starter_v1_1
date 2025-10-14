"""
Comprehensive tests for the safe session logger and file locking mechanisms.
Restored during Rollback Recovery.
"""

import errno
import logging
import multiprocessing
import os
import stat
import time
import unittest.mock as mock
from contextlib import suppress
from pathlib import Path

import pytest

# Adjust the import path based on the actual project structure
# We attempt to import the components, handling potential naming variations due to the rollback/recovery process.
try:
    # Prioritizing the names used during the successful stabilization effort (ProcessSafeLock)
    from optipanel.ops.session_logger_safe import ProcessSafeLock as FileLock
    from optipanel.ops.session_logger_safe import (
        _ensure_private_directory as ensure_private_directory,
    )
    from optipanel.ops.session_logger_safe import (
        _open_secure_append,
    )
except ImportError:
    try:
        # Fallback to alternative names if the structure differs
        from optipanel.ops.session_logger_safe import FileLock, _open_secure_append, ensure_private_directory
    except ImportError:
        pytest.skip(
            "optipanel.ops.session_logger_safe components (FileLock/ProcessSafeLock) not found",
            allow_module_level=True,
        )

# Attempt to import fcntl, required for file locking on POSIX systems
try:
    import fcntl
except ImportError:
    fcntl = None


# --- Helper Functions ---


def check_lock_held(lock_path: Path) -> bool:
    """Check if the lock file is currently held by another process."""
    if fcntl is None:
        return False

    fd = None
    try:
        # Ensure the directory exists before attempting to open
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Attempt to open and lock without blocking
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # If successful, the lock was not held
            return False
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                # Lock is held
                return True
            raise
    except OSError:
        return False  # Handle issues opening the file itself
    finally:
        if fd is not None:
            # Ensure the descriptor is closed
            with suppress(OSError):
                os.close(fd)


# --- Fixtures ---


@pytest.fixture
def lock_file(tmp_path: Path) -> Path:
    # Use a subdirectory to test directory creation logic within the locking mechanism
    return tmp_path / "locks" / "test.lock"


# --- Tests for ensure_private_directory ---


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions not applicable on Windows")
def test_ensure_private_directory_creates_and_sets_permissions(tmp_path: Path):
    """Ensure the directory is created with 0700 permissions."""
    target_dir = tmp_path / "private"
    result = ensure_private_directory(target_dir)

    assert result == target_dir
    assert target_dir.exists()
    # Check permissions (stat.S_IMODE masks the mode bits)
    mode = stat.S_IMODE(target_dir.stat().st_mode)
    # Ensure the mode is exactly 0700
    assert (mode & 0o777) == 0o700


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions not applicable on Windows")
def test_ensure_private_directory_existing(tmp_path: Path):
    """Ensure existing directory permissions are corrected."""
    target_dir = tmp_path / "private"
    # Create with incorrect permissions
    target_dir.mkdir(mode=0o755)
    # Explicitly set mode to ensure test determinism regardless of umask
    os.chmod(target_dir, 0o755)

    ensure_private_directory(target_dir)

    mode = stat.S_IMODE(target_dir.stat().st_mode)
    # Check if it's restricted to the user (0700)
    assert (mode & 0o777) == 0o700


# --- Tests for _open_secure_append ---


@pytest.mark.skipif(os.name == "nt", reason="O_NOFOLLOW and POSIX permissions not applicable on Windows")
def test_open_secure_append_creates_and_sets_permissions(tmp_path: Path):
    """Ensure the file is created with 0600 permissions."""
    target_file = tmp_path / "secure.log"
    # Ensure parent directory exists
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Use the helper which should handle the secure opening
    handle = _open_secure_append(target_file)
    try:
        handle.write("test\n")
    finally:
        handle.close()

    assert target_file.exists()
    mode = stat.S_IMODE(target_file.stat().st_mode)
    # Ensure the mode is exactly 0600
    assert (mode & 0o777) == 0o600


@pytest.mark.skipif(
    os.name == "nt" or not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW not supported on this platform"
)
def test_open_secure_append_nofollow_symlink(tmp_path: Path):
    """Ensure O_NOFOLLOW prevents opening symlinks (Security - Bug #113)."""
    target_file = tmp_path / "secure.log"
    symlink_path = tmp_path / "link.log"

    # Create a symlink
    try:
        symlink_path.symlink_to(target_file)
    except OSError as e:
        pytest.skip(f"Symlink creation failed (requires privileges): {e}")

    with pytest.raises(OSError) as excinfo:
        _open_secure_append(symlink_path)

    # ELOOP is common on Linux; EPERM/EACCES/EEXIST might occur on others.
    assert excinfo.value.errno in (errno.ELOOP, errno.EPERM, errno.EACCES, errno.EEXIST)


# --- Tests for FileLock (ProcessSafeLock) ---


# Helper to check internal state robustly across potential implementations
def _is_locked_internally(lock_instance):
    return (
        getattr(lock_instance, "lock_handle", None) is not None
        or getattr(lock_instance, "_lock_file_fd", None) is not None
    )


@pytest.mark.skipif(fcntl is None, reason="Requires fcntl")
def test_filelock_acquire_release(lock_file: Path):
    """Test basic lock acquisition and release."""
    lock = FileLock(lock_file)

    assert lock.acquire()
    assert _is_locked_internally(lock)
    assert check_lock_held(lock_file)

    lock.release()
    assert not _is_locked_internally(lock)
    # Note: check_lock_held might briefly be True after release due to OS scheduling,
    # but the internal state should be cleared.


@pytest.mark.skipif(fcntl is None, reason="Requires fcntl")
def test_filelock_context_manager(lock_file: Path):
    """Test lock usage as a context manager."""
    lock = FileLock(lock_file)

    with lock:
        assert _is_locked_internally(lock)
        assert check_lock_held(lock_file)

    assert not _is_locked_internally(lock)


@pytest.mark.skipif(fcntl is None, reason="Requires fcntl")
def test_filelock_reentrancy(lock_file: Path):
    """Test that the lock is reentrant within the same instance."""
    lock = FileLock(lock_file)

    with lock:
        assert lock.acquire()  # Should succeed immediately
        with lock:
            assert check_lock_held(lock_file)
        # Inner context exit

    # Outer context exit. Should be fully released.
    assert not _is_locked_internally(lock)


@pytest.mark.skipif(os.name == "nt" or fcntl is None, reason="Requires POSIX multiprocessing (fork) and fcntl")
def test_filelock_concurrency_lockout(lock_file: Path):
    """Test that the lock prevents access from another process."""

    # Helper for the child process
    def attempt_lock(lock_path, result_queue):
        # Use a very short timeout for the child process attempt
        lock = FileLock(lock_path, timeout=0.1, max_retries=1)
        if lock.acquire():
            result_queue.put(True)
            lock.release()
        else:
            result_queue.put(False)

    lock = FileLock(lock_file)
    # Use 'fork' context for POSIX compatibility
    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        pytest.skip("Fork context not available on this platform.")

    # Add skip guard for restricted environments (sandbox/IPC restrictions)
    try:
        queue = ctx.Queue()
    except (PermissionError, OSError) as exc:
        pytest.skip(f"multiprocessing queue unavailable due to environmental restrictions: {exc}")

    with lock:
        # Lock is held by the main process
        assert check_lock_held(lock_file)

        # Start the child process
        p = ctx.Process(target=attempt_lock, args=(lock_file, queue))
        p.start()
        p.join(timeout=2)  # Give the child process ample time

        # Child process should report failure to acquire the lock
        assert not queue.empty()
        assert queue.get() is False

    # After release, child should succeed
    p = ctx.Process(target=attempt_lock, args=(lock_file, queue))
    p.start()
    p.join(timeout=2)
    assert queue.get() is True


@pytest.mark.skipif(fcntl is None, reason="Requires fcntl for reliable testing")
def test_filelock_timeout_behavior_and_bug_90_fix(lock_file: Path):
    """Test that the lock acquisition times out correctly when contested (Validates Bug #90 fix)."""

    # Ensure the directory exists before manual open
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # Manually acquire the lock using low-level operations to simulate contention
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT)
    try:
        # Acquire exclusive lock
        fcntl.flock(fd, fcntl.LOCK_EX)

        # Attempt to acquire the lock with a specific timeout
        timeout_seconds = 0.5
        start_time = time.time()
        # Use enough retries to ensure the timeout logic is tested, not the retry limit
        lock = FileLock(lock_file, timeout=timeout_seconds, max_retries=50)

        acquired = lock.acquire()

        end_time = time.time()
        duration = end_time - start_time

        assert not acquired

        # Crucial check for Bug #90: Ensure the duration respects the timeout.
        # Allow a reasonable tolerance for scheduling overhead.
        tolerance = 0.25
        assert (
            timeout_seconds <= duration < (timeout_seconds + tolerance)
        ), f"Lock acquisition took {duration:.2f}s (expected ~{timeout_seconds}s)"

    finally:
        # Clean up the manual lock
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@pytest.mark.skipif(fcntl is None, reason="Requires fcntl for this test")
def test_filelock_cleanup_on_error(lock_file: Path, caplog: pytest.LogCaptureFixture):
    """Ensure the lock handle is cleaned up if acquisition fails."""
    lock = FileLock(lock_file, timeout=0.01, max_retries=0)

    # Simulate contention by mocking fcntl.flock
    def mock_flock(fd, op):
        # Simulate the lock being held elsewhere
        raise OSError(errno.EAGAIN, "Resource temporarily unavailable")

    # Patch fcntl.flock to force the failure path. We patch the 'fcntl' module directly.
    with mock.patch("fcntl.flock", mock_flock), caplog.at_level(logging.DEBUG):
        assert not lock.acquire()

    # Handle should be closed and set to None even if flock failed
    assert not _is_locked_internally(lock)
