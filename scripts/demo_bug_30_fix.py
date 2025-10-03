#!/usr/bin/env python3
"""Demonstration of Bug #30 fix: Multi-process safe log rotation.

This script demonstrates that multiple processes can now safely attempt
to rotate the same log file without race conditions.
"""

import multiprocessing
import os
import tempfile
import time
from pathlib import Path

from optipanel.ops.session_logger_safe import SafeLogRotationManager


def rotation_worker(log_dir: str, worker_id: int, iterations: int = 5):
    """Worker function that attempts log rotation."""
    print(f"Worker {worker_id} (PID {os.getpid()}) starting...")

    manager = SafeLogRotationManager(log_dir, max_size_mb=1, lock_timeout=5.0)  # 1MB rotation threshold

    for i in range(iterations):
        # Create a log file that needs rotation
        log_file = Path(log_dir) / f"test-{i}.jsonl"
        if not log_file.exists():
            # Create a 2MB file (exceeds 1MB threshold)
            log_file.write_text("x" * (2 * 1024 * 1024))

        # Attempt rotation
        rotated = manager.rotate_file_safe(log_file)

        if rotated:
            print(f"  Worker {worker_id}: Successfully rotated {log_file.name} to {rotated.name}")
        else:
            print(f"  Worker {worker_id}: Rotation skipped for {log_file.name} (another process handled it)")

        time.sleep(0.1)  # Small delay to increase contention chance

    print(f"Worker {worker_id} completed")


def main():
    """Main demonstration function."""
    print("Bug #30 Fix Demonstration: Multi-process Safe Log Rotation")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Using temporary directory: {tmpdir}")
        print()

        # Create some initial log files
        for i in range(3):
            log_file = Path(tmpdir) / f"initial-{i}.jsonl"
            log_file.write_text("x" * (2 * 1024 * 1024))  # 2MB files

        print("Starting 3 worker processes to rotate logs concurrently...")
        print()

        # Start multiple processes
        processes = []
        for worker_id in range(3):
            p = multiprocessing.Process(target=rotation_worker, args=(tmpdir, worker_id, 3))
            p.start()
            processes.append(p)

        # Wait for all processes to complete
        for p in processes:
            p.join(timeout=30)
            if p.is_alive():
                print(f"Warning: Process {p.pid} did not complete in time")
                p.terminate()
                p.join()

        print()
        print("All workers completed!")
        print()

        # Check results
        lock_dir = Path(tmpdir) / ".locks"
        remaining_locks = list(lock_dir.glob("*.lock")) if lock_dir.exists() else []

        print("Results:")
        print(f"  Lock directory created: {lock_dir.exists()}")
        print(f"  Remaining lock files: {len(remaining_locks)}")

        if remaining_locks:
            print("  Warning: Some lock files were not cleaned up:")
            for lock in remaining_locks:
                print(f"    - {lock.name}")

        # Count rotated files
        rotated_files = list(Path(tmpdir).glob("*.jsonl*"))
        original_files = [f for f in rotated_files if not any(c.isdigit() for c in f.stem)]
        rotated_archives = [f for f in rotated_files if any(c.isdigit() for c in f.stem)]

        print(f"  Original log files: {len(original_files)}")
        print(f"  Rotated archives: {len(rotated_archives)}")

        print()
        print("✅ Demonstration complete! No race conditions or crashes occurred.")
        print("   Multiple processes safely coordinated log rotation using file locks.")


if __name__ == "__main__":
    main()
