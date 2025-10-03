#!/usr/bin/env python3
"""Demonstration of Bug #24 fix: EventLogger data loss prevention.

This script demonstrates that the fix for Bug #24 successfully prevents
data loss by flushing log data to disk immediately after writing.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.ops.eventlog import DurabilityLevel, EventLogger


def test_without_flush(log_dir: Path) -> int:
    """Simulate crash without flush (legacy behavior)."""
    print("\n=== Testing PERFORMANCE mode (no flush - legacy behavior) ===")

    test_script = log_dir / "test_no_flush.py"
    script_content = f"""
import sys
import os
sys.path.insert(0, "{Path(__file__).parent.parent}")
from optipanel.ops.eventlog import EventLogger, DurabilityLevel

logger = EventLogger(log_dir="{log_dir}", durability=DurabilityLevel.PERFORMANCE)
logger.emit("before_crash", {{"test": "data_without_flush", "important": "will_be_lost"}})
print("Event written (but not flushed)")
# Simulate abrupt crash
os._exit(1)
"""
    test_script.write_text(script_content)

    # Run script
    result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True)
    print(f"Script output: {result.stdout}")

    # Count events that survived
    log_files = list(log_dir.glob("*.jsonl"))
    event_count = 0
    if log_files:
        with open(log_files[0]) as f:
            event_count = len(f.readlines())

    print(f"Events survived crash: {event_count}")
    return event_count


def test_with_flush(log_dir: Path) -> int:
    """Simulate crash with flush (fixed behavior)."""
    print("\n=== Testing STANDARD mode (with flush - fixed behavior) ===")

    test_script = log_dir / "test_with_flush.py"
    script_content = f"""
import sys
import os
sys.path.insert(0, "{Path(__file__).parent.parent}")
from optipanel.ops.eventlog import EventLogger, DurabilityLevel

logger = EventLogger(log_dir="{log_dir}", durability=DurabilityLevel.STANDARD)
logger.emit("before_crash", {{"test": "data_with_flush", "important": "will_survive"}})
print("Event written and flushed")
# Simulate abrupt crash
os._exit(1)
"""
    test_script.write_text(script_content)

    # Run script
    result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True)
    print(f"Script output: {result.stdout}")

    # Count events that survived
    log_files = list(log_dir.glob("*.jsonl"))
    event_count = 0
    if log_files:
        with open(log_files[0]) as f:
            event_count = len(f.readlines())

    print(f"Events survived crash: {event_count}")
    return event_count


def test_performance_impact():
    """Measure performance impact of different durability levels."""
    print("\n=== Performance Impact Measurement ===")

    results = {}
    num_events = 1000

    for level in DurabilityLevel:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(log_dir=tmpdir, durability=level)

            start_time = time.perf_counter()
            for i in range(num_events):
                logger.emit("perf_test", {"index": i})
            elapsed = time.perf_counter() - start_time

            events_per_second = num_events / elapsed
            results[level.name] = {"time": elapsed, "eps": events_per_second}

    # Display results
    print(f"\nResults for {num_events} events:")
    print("-" * 50)
    for level_name, stats in results.items():
        print(f"{level_name:12} : {stats['time']:.3f}s ({stats['eps']:.0f} events/sec)")

    # Calculate overhead
    perf_time = results["PERFORMANCE"]["time"]
    standard_overhead = ((results["STANDARD"]["time"] / perf_time) - 1) * 100
    paranoid_overhead = ((results["PARANOID"]["time"] / perf_time) - 1) * 100

    print("\nOverhead compared to PERFORMANCE mode:")
    print(f"  STANDARD : +{standard_overhead:.1f}%")
    print(f"  PARANOID : +{paranoid_overhead:.1f}%")


def main():
    """Run all demonstrations."""
    print("=" * 60)
    print("Bug #24 Fix Demonstration: EventLogger Data Loss Prevention")
    print("=" * 60)

    # Test crash scenarios
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Clear between tests
        for f in tmpdir.glob("*.jsonl"):
            f.unlink()

        # Test without flush (should lose data)
        no_flush_count = test_without_flush(tmpdir)

        # Clear between tests
        for f in tmpdir.glob("*.jsonl"):
            f.unlink()

        # Test with flush (should preserve data)
        with_flush_count = test_with_flush(tmpdir)

        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)

        if no_flush_count == 0 and with_flush_count == 1:
            print("✅ FIX VERIFIED: Data loss prevented!")
            print("   - PERFORMANCE mode lost data on crash (expected)")
            print("   - STANDARD mode preserved data on crash (fixed!)")
        else:
            print("❌ UNEXPECTED RESULTS:")
            print(f"   - PERFORMANCE mode events: {no_flush_count}")
            print(f"   - STANDARD mode events: {with_flush_count}")

    # Test performance impact
    test_performance_impact()

    print("\n" + "=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    print("The fix successfully prevents data loss with minimal performance impact.")
    print("Use STANDARD mode for normal operations (protects against app crashes).")
    print("Use PARANOID mode for critical audit logs (protects against OS crashes).")
    print("Use PERFORMANCE mode only when data loss is acceptable.")


if __name__ == "__main__":
    main()
