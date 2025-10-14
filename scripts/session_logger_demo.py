#!/usr/bin/env python3
"""Demonstrate the enhanced session logging capabilities."""

import json
import time
from pathlib import Path

from optipanel.ops.session_logger import (
    LogRotationManager,
    SessionLogger,
    get_session_logger,
)


def demo_basic_session():
    """Demonstrate basic session logging."""
    print("=== Basic Session Demo ===")

    with get_session_logger(command="demo_basic") as logger:
        print(f"Session ID: {logger.session_id}")

        # Log some operations
        with logger.operation_context("data_fetch", source="api"):
            time.sleep(0.1)  # Simulate work
            logger.emit("data_received", {"records": 100})

        # Log metrics
        logger.emit_metric("api_latency", 95.5, unit="ms")
        logger.emit_metric("cache_hit_rate", 0.85, unit="ratio")

        # Simulate an error (but handle it)
        try:
            raise ValueError("Simulated error")
        except ValueError as e:
            logger.emit_error(
                "validation_error",
                "Data validation failed",
                details={"field": "price"},
                exception=e,
            )

    print("Session completed successfully\n")


def demo_nested_operations():
    """Demonstrate nested operation contexts."""
    print("=== Nested Operations Demo ===")

    logger = SessionLogger(command="demo_nested")

    with logger.operation_context("batch_process", batch_size=50):
        logger.emit("batch_started", {"size": 50})

        for i in range(3):
            with logger.operation_context("process_item", item_id=i):
                time.sleep(0.05)  # Simulate work
                logger.emit("item_processed", {"item_id": i, "status": "success"})

        logger.emit("batch_completed", {"processed": 3})

    logger.finalize()
    print(f"Nested operations completed (Session: {logger.session_id})\n")


def demo_alert_tracking():
    """Demonstrate alert and recon tracking."""
    print("=== Alert Tracking Demo ===")

    with get_session_logger(command="alert_monitor") as logger:
        # Simulate alert generation
        alerts = [
            {"symbol": "AAPL", "type": "breakout", "strength": 85},
            {"symbol": "MSFT", "type": "trend", "strength": 72},
            {"symbol": "GOOGL", "type": "bounce", "strength": 91},
        ]

        for alert in alerts:
            with logger.operation_context("evaluate_alert", symbol=alert["symbol"]):
                # Log the alert
                logger.emit(
                    "alert",
                    {
                        "symbol": alert["symbol"],
                        "alert_type": alert["type"],
                        "strength": alert["strength"],
                        "threshold_passed": alert["strength"] > 80,
                    },
                )

                # Log decision
                if alert["strength"] > 80:
                    logger.emit(
                        "alert_triggered",
                        {
                            "symbol": alert["symbol"],
                            "action": "notify",
                        },
                    )

        # Summary metrics
        logger.emit_metric("alerts_evaluated", len(alerts))
        logger.emit_metric("alerts_triggered", sum(1 for a in alerts if a["strength"] > 80))

    print("Alert tracking completed\n")


def demo_performance_tracking():
    """Demonstrate performance metric tracking."""
    print("=== Performance Tracking Demo ===")

    logger = SessionLogger(command="performance_test")

    # Simulate multiple operations with varying durations
    operations = ["fetch_data", "compute_indicators", "generate_signals", "send_notifications"]

    for op_name in operations:
        for i in range(3):
            with logger.operation_context(op_name, iteration=i):
                # Varying sleep to simulate different durations
                time.sleep(0.01 * (i + 1))

    # The metrics are automatically tracked
    logger.finalize()

    # Show collected metrics
    print("Collected Metrics:")
    for op_name, metrics in logger._metadata.metrics.items():
        if metrics["count"] > 0:
            print(f"  {op_name}:")
            print(f"    Count: {metrics['count']}")
            print(f"    Avg: {metrics['avg_ms']:.2f}ms")
            print(f"    Min: {metrics['min_ms']:.2f}ms")
            print(f"    Max: {metrics['max_ms']:.2f}ms")

    print()


def demo_log_rotation():
    """Demonstrate log rotation management."""
    print("=== Log Rotation Demo ===")

    # Create test log directory
    log_dir = Path("./test_logs")
    log_dir.mkdir(exist_ok=True)

    # Create some test log files
    test_file = log_dir / "events-20240101.jsonl"
    test_file.write_text("x" * (1024 * 100))  # 100KB file
    print(f"Created test file: {test_file} ({test_file.stat().st_size} bytes)")

    # Set up rotation manager
    manager = LogRotationManager(
        str(log_dir),
        max_size_mb=0.05,  # 50KB for demo
        max_age_days=30,
        max_files=5,
    )

    # Check if rotation is needed
    if manager.should_rotate(test_file):
        print("File exceeds size limit, rotating...")
        rotated = manager.rotate_file(test_file)
        print(f"Rotated to: {rotated}")

    # Cleanup
    for f in log_dir.glob("*"):
        f.unlink()
    log_dir.rmdir()
    print("Cleanup completed\n")


def show_session_logs():
    """Display recent session events from logs."""
    print("=== Recent Session Events ===")

    logger = SessionLogger(command="viewer")

    # Find today's event file
    today_file = logger._path_for_today()

    if today_file.exists():
        print(f"Reading from: {today_file}\n")

        # Read and categorize events
        session_events = {}
        with open(today_file) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    session_id = event.get("session_id", "unknown")

                    if session_id not in session_events:
                        session_events[session_id] = {
                            "command": event.get("command", "unknown"),
                            "events": [],
                            "error_count": 0,
                            "start_time": None,
                            "end_time": None,
                        }

                    session_events[session_id]["events"].append(event)

                    if event.get("kind") == "error":
                        session_events[session_id]["error_count"] += 1

                    if event.get("event_type") == "session_start":
                        session_events[session_id]["start_time"] = event.get("ts")

                    if event.get("event_type") == "session_end":
                        session_events[session_id]["end_time"] = event.get("ts")
                        session_events[session_id]["duration"] = event.get("duration_seconds")
                        session_events[session_id]["status"] = event.get("status")

                except json.JSONDecodeError:
                    pass

        # Display summary
        for session_id, info in list(session_events.items())[-5:]:  # Last 5 sessions
            print(f"Session: {session_id}")
            print(f"  Command: {info['command']}")
            print(f"  Events: {len(info['events'])}")
            print(f"  Errors: {info['error_count']}")

            if "duration" in info:
                print(f"  Duration: {info['duration']:.2f}s")
                print(f"  Status: {info.get('status', 'unknown')}")

            print()
    else:
        print(f"No events file found at: {today_file}")

    logger.finalize()


def main():
    """Run all demos."""
    demos = [
        demo_basic_session,
        demo_nested_operations,
        demo_alert_tracking,
        demo_performance_tracking,
        demo_log_rotation,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"Demo failed: {e}\n")

    # Show the collected logs
    show_session_logs()


if __name__ == "__main__":
    main()
