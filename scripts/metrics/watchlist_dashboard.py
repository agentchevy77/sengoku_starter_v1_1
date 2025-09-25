#!/usr/bin/env python3
"""Aggregate `watchlist_*` events for dashboarding.

Reads JSONL event logs and produces summary statistics that can be fed into
Grafana (via textfile exporters) or inspected manually. Output format:

```
watchlists_processed <count>
watchlists_alerts_total <count>
watchlists_render_backoff <count>
```

Use `--as-json` for structured output.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

WATCHLIST_PROCESSED = "watchlist_processed"
WATCHLIST_RENDERED = "watchlist_rendered"


def iter_events(paths: Iterable[Path]) -> Iterable[dict[str, object]]:
    """Yield JSON event payloads from the given log file paths."""

    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event


def summarize(log_dir: Path, *, window_files: int) -> dict[str, int]:
    """Aggregate recent watchlist events into a compact metrics dictionary."""

    files = sorted(log_dir.glob("events-*.jsonl"), reverse=True)[:window_files]
    counters: Counter[str] = Counter()

    for event in iter_events(files):
        kind = event.get("kind")
        if kind != WATCHLIST_PROCESSED and kind != WATCHLIST_RENDERED:
            continue
        if kind == WATCHLIST_PROCESSED:
            counters["watchlists_processed"] += 1
            # Safe integer conversion with error handling
            try:
                alerts_value = event.get("alerts", 0)
                counters["alerts_total"] += int(alerts_value) if alerts_value else 0
            except (ValueError, TypeError):
                # Log but don't crash on bad data
                counters["alerts_total"] += 0
        else:
            if bool(event.get("backoff")):
                counters["render_backoff"] += 1

    return {
        "watchlists_processed": counters["watchlists_processed"],
        "watchlists_alerts_total": counters["alerts_total"],
        "watchlists_render_backoff": counters["render_backoff"],
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the metrics exporter."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir",
        default=os.getenv("SENGOKU_LOG_DIR", "./runs"),
        help="Directory containing events-*.jsonl files",
    )
    parser.add_argument(
        "--files",
        type=int,
        default=5,
        help="Number of most-recent files to scan (default: 5)",
    )
    parser.add_argument(
        "--as-json",
        action="store_true",
        help="Emit JSON instead of plain text",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point returning a POSIX-style exit status."""

    args = parse_args()
    log_dir = Path(args.log_dir).resolve()
    metrics = summarize(log_dir, window_files=max(1, args.files))

    if args.as_json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        for key, value in metrics.items():
            print(f"{key} {value}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
