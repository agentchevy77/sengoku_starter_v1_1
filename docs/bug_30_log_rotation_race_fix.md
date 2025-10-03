# Bug #30: Multi-Process Race Condition in Log Rotation - FIXED

## Problem Summary
The `SafeLogRotationManager` in `optipanel/ops/session_logger_safe.py` used only `threading.Lock()` which provides thread safety within a single process but not across multiple processes. This led to race conditions when multiple processes attempted to rotate the same log file simultaneously, potentially causing:
- Data loss during rotation
- Corrupted log files
- Failed rotations
- Process crashes

## Root Cause Analysis
1. **Inadequate Locking**: `threading.Lock()` only works within a single process
2. **TOCTOU Vulnerability**: Time-of-check-time-of-use issues between file existence checks and operations
3. **Non-atomic Operations**: Multiple steps (rename, compress, delete) weren't atomic across processes
4. **No Lock File Management**: No mechanism to clean up stale lock files

## Solution Architecture

### 1. ProcessSafeLock Class
Implemented a cross-process file-based locking mechanism using `fcntl.flock()` on Unix systems:
- **Exclusive Locking**: Uses `fcntl.LOCK_EX | fcntl.LOCK_NB` for non-blocking exclusive locks
- **Exponential Backoff**: Implements retry logic with jitter to reduce contention
- **Graceful Degradation**: Falls back safely if locking fails
- **Lock File Management**: Separate `.locks` directory to avoid interfering with log data

### 2. Enhanced SafeLogRotationManager
Updated to use ProcessSafeLock for all file operations:
- **Per-file Locks**: Each log file gets its own lock file for rotation
- **Global Cleanup Lock**: Prevents concurrent cleanup operations
- **Double-checking**: Re-verifies file state after acquiring lock
- **Stale Lock Cleanup**: Automatically removes lock files older than 1 hour

## Implementation Details

### Key Changes:
1. Added `fcntl` import for Unix file locking
2. Created `ProcessSafeLock` class with context manager support
3. Modified `rotate_file_safe()` to use process-safe locking
4. Modified `cleanup_old_files_safe()` to use process-safe locking
5. Added `_cleanup_old_locks()` method for lock file maintenance
6. Enhanced error handling and logging

### Lock File Strategy:
- Lock files stored in `{log_dir}/.locks/`
- Lock file naming: `{original_filename}.lock` for rotation
- Special locks: `cleanup.lock` for cleanup operations
- PID written to lock file for debugging

## Testing
Comprehensive test suite (`tests/test_bug_30_log_rotation_race.py`) verifies:
- Single process lock acquisition/release
- Lock timeout behavior
- Context manager functionality
- Concurrent rotation safety across multiple processes
- Cleanup operation safety
- Stale lock file cleanup
- Stress testing with multiple concurrent operations

## Performance Impact
- **Minimal overhead**: Lock acquisition typically < 10ms
- **Exponential backoff**: Reduces CPU usage during contention
- **Non-blocking**: Operations fail fast if lock unavailable
- **Configurable timeout**: Default 10s, adjustable per use case

## Compatibility
- **Unix/Linux**: Full support via `fcntl`
- **Windows**: Would require `msvcrt` implementation (not included)
- **Backward compatible**: No API changes to existing code

## Risk Mitigation
- **Graceful failure**: Operations skip if lock acquisition fails
- **No deadlocks**: Non-blocking locks with timeouts
- **Automatic cleanup**: Stale locks removed after 1 hour
- **Logging**: All lock failures logged to stderr for monitoring

## Verification
All tests pass successfully:
```
============================== 10 passed in 1.42s ==============================
```

## Status
✅ **FIXED** - The multi-process race condition in log rotation has been successfully resolved.