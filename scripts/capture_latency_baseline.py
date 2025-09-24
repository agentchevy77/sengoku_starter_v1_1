#!/usr/bin/env python3
"""Capture baseline latency metrics for core Sengoku CLI flows.

The script is intended to run before and after the Textual/FastAPI prototype so
we can quantify the impact of the new UI.  Results default to
``./reports/latency-baseline.json``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from optipanel.perf.latency_probe import capture_baseline

DEFAULT_COMMANDS: tuple[Sequence[str], ...] = (
    ("sengoku", "recon", "--help"),
    ("sengoku", "notify", "--help"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=Path("reports/latency-baseline.json"),
        type=Path,
        help="Where to write the JSON report (default: reports/latency-baseline.json)",
    )
    parser.add_argument(
        "--repeats",
        default=3,
        type=int,
        help="How many times to run each command (default: 3)",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command override; pass e.g. -- command args...",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands: tuple[Sequence[str], ...] = (tuple(args.command),) if args.command else DEFAULT_COMMANDS

    capture_baseline(commands, repeats=max(1, int(args.repeats)), output=args.output)
    print(f"Latency report written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
