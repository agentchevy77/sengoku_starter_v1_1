#!/usr/bin/env python3
"""Safety regression demo for SafeSessionLogger.

The legacy implementation has been fully removed from the codebase. This
script now focuses on exercising the hardened logger in scenarios that used to
explode: concurrency, error propagation, bounded metrics, JSON coercion, and
log rotation.
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from pathlib import Path

# Add repository root to sys.path so the script works when executed directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.ops.session_logger_safe import SafeLogRotationManager, SafeSessionLogger


def demo_thread_safety() -> None:
    """Run concurrent operations and show the logger stays consistent."""
    print("\n=== Thread Safety Demo ===")

    def concurrent_operations(logger: SafeSessionLogger, thread_id: int) -> None:
        for i in range(10):
            with logger.operation_context(f"op_{thread_id}_{i}", thread=thread_id):
                time.sleep(0.001)
                logger.emit("event", {"thread": thread_id, "iteration": i})

    logger = SafeSessionLogger(command="safe_concurrent")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futs = [executor.submit(concurrent_operations, logger, idx) for idx in range(5)]
        concurrent.futures.wait(futs)

    print(f"Events logged: {logger._metadata.event_count}")
    print(f"Metrics tracked: {len(logger._metadata.metrics)}")
    print(f"Context depth after run: {len(logger._context_stack)} (expected 0)")
    logger.finalize()


def demo_exception_propagation() -> None:
    """Show that the original exception survives the context manager."""
    print("\n=== Exception Propagation Demo ===")

    try:
        with SafeSessionLogger(command="safe_failing"):
            raise ValueError("Original error")
    except Exception as exc:
        print(f"Raised exception: {type(exc).__name__}: {exc}")
    else:  # pragma: no cover - defensive guard
        print("Unexpected success — expected ValueError to propagate")


def demo_memory_limits() -> None:
    """Demonstrate bounded metric history."""
    print("\n=== Metric Bounding Demo ===")

    logger = SafeSessionLogger(command="memory_test", max_metrics=1000)
    for i in range(1500):
        with logger.operation_context(f"unique_op_{i}"):
            pass
    print(f"Metrics retained: {len(logger._metadata.metrics)} (<= 1000 as configured)")
    logger.finalize()


def demo_json_serialisation() -> None:
    """Verify non-serialisable payloads are handled gracefully."""
    print("\n=== JSON Serialisation Demo ===")

    class NonSerializable:
        def __init__(self) -> None:
            self.payload = b"binary data"
            self.circular = self

    data = {
        "bytes": b"raw bytes",
        "set": {1, 2, 3},
        "object": NonSerializable(),
        "circular": {"self": None},
    }
    data["circular"]["self"] = data["circular"]

    logger = SafeSessionLogger(command="json_test")
    path = logger.emit("test", data)
    print(f"Payload logged to: {path}")
    logger.finalize()

    # Show the result for transparency.
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("command") == "json_test":
                print("Event snippet:", json.dumps(event, indent=2, sort_keys=True))
                break


def demo_context_depth() -> None:
    """Confirm the guard against runaway recursion."""
    print("\n=== Context Depth Demo ===")

    def nested(logger: SafeSessionLogger, depth: int) -> None:
        if depth <= 0:
            return
        with logger.operation_context(f"depth_{depth}"):
            nested(logger, depth - 1)

    logger = SafeSessionLogger(command="depth_test", max_context_depth=10)
    nested(logger, 20)
    logger.finalize()
    print("Nested calls completed without overflowing the context stack.")


def demo_log_rotation() -> None:
    """Rotate a file to prove SafeLogRotationManager works atomically."""
    print("\n=== Log Rotation Demo ===")

    test_dir = Path("./test_rotation")
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "events-20240101.jsonl"
    test_file.write_text('{"test": "data"}\n' * 1000, encoding="utf-8")
    manager = SafeLogRotationManager(str(test_dir), max_size_mb=0.001)

    if manager.should_rotate(test_file):
        rotated = manager.rotate_file_safe(test_file)
        print(f"Rotated file: {rotated}")
    else:  # pragma: no cover - defensive guard
        print("File did not exceed threshold; nothing to rotate")

    # Cleanup temporary artefacts.
    import shutil

    shutil.rmtree(test_dir)
    print("Temporary rotation directory removed.")


def main() -> None:
    print("=" * 60)
    print("SAFE SESSION LOGGER DEMONSTRATION")
    print("=" * 60)

    for demo in (
        demo_thread_safety,
        demo_exception_propagation,
        demo_memory_limits,
        demo_json_serialisation,
        demo_context_depth,
        demo_log_rotation,
    ):
        try:
            demo()
        except Exception as exc:  # pragma: no cover - defensive guard
            print(f"\n!!! Demo {demo.__name__} failed: {exc}")

    print("\n" + "=" * 60)
    print("All demos completed using SafeSessionLogger only.")
    print("=" * 60)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
