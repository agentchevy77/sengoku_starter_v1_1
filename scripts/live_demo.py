#!/usr/bin/env python3

"""One-shot live/paper demo runner for Sengoku."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
from optipanel.monitoring import evaluate_pacing_alerts, load_thresholds_from_env
from optipanel.runtime.health import get_ibkr_health, get_runtime_health
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room


def _parse_symbols(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def run_demo(symbols: Sequence[str], output_dir: Path, width: int, top_n: int, ping: bool) -> int:
    if not symbols:
        print("[demo] provide at least one symbol via --symbols", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = cfg_from_env()
    fetcher = RealTwsFetcher(cfg)
    if ping:
        print("[demo] performing handshake...", file=sys.stderr)
        try:
            fetcher.handshake_test()
        except Exception as exc:  # noqa: BLE001 - present to user
            print(f"[demo] handshake failed: {exc}", file=sys.stderr)

    print(f"[demo] fetching features for {', '.join(symbols)}", file=sys.stderr)
    features = fetcher.features_for_symbols(list(symbols))
    _write_json(output_dir / "features.json", features)

    print("[demo] running command room snapshot", file=sys.stderr)
    tick = run_once({sym: features.get(sym, {}) for sym in symbols})
    _write_json(output_dir / "run_once.json", tick)

    panel = render_command_room(tick, width=width, top_n=top_n)
    (output_dir / "command_room.txt").write_text(panel)

    pacing_metrics = fetcher.pacing_metrics()
    overrides = load_thresholds_from_env()
    pacing_alerts = [asdict(a) for a in evaluate_pacing_alerts(pacing_metrics, thresholds=overrides or None)]

    ibkr_health = get_ibkr_health(fetcher)
    ibkr_health["pacing"] = pacing_metrics
    if pacing_alerts:
        ibkr_health["pacing_alerts"] = pacing_alerts
    if overrides:
        ibkr_health["pacing_thresholds"] = overrides

    snapshot = get_runtime_health(extra={"ibkr": ibkr_health, "symbols": list(symbols)})
    _write_json(output_dir / "health.json", snapshot)

    print("[demo] outputs written to", output_dir, file=sys.stderr)
    print(panel)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a one-shot Sengoku live demo")
    parser.add_argument("--symbols", required=True, help="Comma separated list, e.g. AAPL,MSFT,SPY")
    parser.add_argument("--output-root", default="logs", help="Directory to store demo outputs")
    parser.add_argument("--width", type=int, default=32, help="Command room width")
    parser.add_argument("--top-n", type=int, default=3, help="Number of symbols to highlight")
    parser.add_argument("--no-ping", action="store_true", help="Skip handshake() warm-up")
    args = parser.parse_args(argv)

    symbols = _parse_symbols(args.symbols)
    root = Path(args.output_root).expanduser().resolve()
    demo_dir = root / f"live-demo-{_timestamp()}"
    return run_demo(symbols, demo_dir, args.width, args.top_n, ping=not args.no_ping)


if __name__ == "__main__":
    raise SystemExit(main())
