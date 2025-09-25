#!/usr/bin/env python3
"""Check for legacy logger usage in recent logs.

This monitoring script scans recent event logs for any `logger_type="legacy"`
metrics, which would indicate a regression to the unsafe implementation.

Exit codes:
  0: No legacy usage detected (good)
  1: Legacy usage detected (alert needed)
  2: Error reading logs
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_for_legacy_usage(log_dir: Path, days_back: int = 1) -> int:
    """Scan recent logs for legacy logger usage."""

    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(days=days_back)
    cutoff_timestamp = cutoff_time.timestamp()

    legacy_found = False
    events_checked = 0

    try:
        # Check all recent event files
        for log_file in sorted(log_dir.glob("events-*.jsonl")):
            # Skip files older than cutoff (based on filename)
            try:
                parts = log_file.stem.split("-", 1)
                if len(parts) < 2:
                    raise ValueError("missing date segment")
                date_str = parts[1]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                if file_date < cutoff_time.replace(hour=0, minute=0, second=0, microsecond=0):
                    continue
            except (IndexError, ValueError):
                # If we can't parse the date, check the file anyway
                pass

            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        events_checked += 1

                        # Check if this is a logger_type metric
                        if event.get("kind") == "metric" and event.get("metric") == "logger_type":

                            # Check timestamp if available
                            if "ts" in event and event["ts"] < cutoff_timestamp:
                                continue

                            value = event.get("value")
                            if value == "legacy":
                                legacy_found = True
                                print(f"WARNING: Legacy logger detected in {log_file.name}")
                                print(f"  Session: {event.get('session_id', 'unknown')}")
                                print(f"  Command: {event.get('command', 'unknown')}")
                                print(f"  Time: {datetime.fromtimestamp(event.get('ts', 0))}")

                    except json.JSONDecodeError:
                        # Skip malformed lines
                        pass

        if events_checked == 0:
            print(f"No events found in {log_dir} for the last {days_back} day(s)")
            return 2

        if not legacy_found:
            print(f"✓ No legacy logger usage detected ({events_checked} events checked)")
            return 0
        else:
            print("\n✗ Legacy logger usage detected! This should not happen.")
            print("  All code should use get_session_logger() which returns SafeSessionLogger")
            return 1

    except Exception as e:
        print(f"Error reading logs: {e}", file=sys.stderr)
        return 2


def main():
    """Main entry point."""
    log_dir = Path(os.getenv("SENGOKU_LOG_DIR", "./runs"))

    if not log_dir.exists():
        print(f"Log directory {log_dir} does not exist")
        return 2

    # Check last 7 days by default
    days = int(os.getenv("CHECK_DAYS", "7"))

    return check_for_legacy_usage(log_dir, days)


if __name__ == "__main__":
    sys.exit(main())
