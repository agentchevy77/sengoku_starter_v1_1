#!/usr/bin/env python3
"""Display the status of high-performance runtime dependencies."""

from __future__ import annotations

from optipanel.perf.runtime_checks import collect_runtime_summary


def main() -> int:
    summary = collect_runtime_summary()

    print("Performance Runtime Summary:\n")
    for status in (summary.orjson, summary.uvloop, summary.aiofiles):
        marker = "✅" if status.installed else "❌"
        version = status.version or "missing"
        print(f"{marker} {status.name:<8} -> {version}")

    print()
    print(f"All fast paths available: {summary.all_fast_paths_available}")
    if summary.orjson.installed:
        print("✅ Orjson active: True")
    else:
        print("⚠️  Orjson active: False")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
