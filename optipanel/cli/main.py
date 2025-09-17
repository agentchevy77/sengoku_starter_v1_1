from __future__ import annotations
import argparse, json
from typing import Dict, Any, List

from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.engine.scan import run_local_scan
from optipanel.alerts.engine import analyze_batch, DEFAULT_THRESH

# --------------------------------------------------------------------------------------
# Programmatic helpers (pure) — used by tests and other Python callers
# --------------------------------------------------------------------------------------
def snapshot_cmd(symbol: str, features: Dict[str, Any]) -> Dict[str, Any]:
    """Return a single symbol snapshot (pure, no printing)."""
    return build_symbol_snapshot(symbol, features)

def scan_cmd(symbols: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Return multi-symbol scan results (pure, no printing)."""
    return run_local_scan(symbols)

def alerts_cmd(symbols: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return alerts for a dict of {symbol: features} (pure, no printing)."""
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]
    return analyze_batch(snaps, DEFAULT_THRESH)

# --------------------------------------------------------------------------------------
# CLI entry points — print JSON and return exit codes
# --------------------------------------------------------------------------------------
def snapshot_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku snapshot")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--features-json", required=True)
    args = ap.parse_args(argv)
    features = json.loads(args.features_json)
    snap = build_symbol_snapshot(args.symbol, features)
    print(json.dumps(snap, indent=2, sort_keys=True))
    return 0

def scan_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku scan")
    ap.add_argument("--symbols-json", required=True)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    out = run_local_scan(symbols)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

def alerts_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku alerts")
    ap.add_argument("--symbols-json", required=True)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]
    alerts = analyze_batch(snaps, DEFAULT_THRESH)
    print(json.dumps(alerts, indent=2, sort_keys=True))
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog="sengoku")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="Print a single symbol snapshot")
    s.add_argument("--symbol", required=True)
    s.add_argument("--features-json", required=True)

    sc = sub.add_parser("scan", help="Rank multiple symbols")
    sc.add_argument("--symbols-json", required=True)

    a = sub.add_parser("alerts", help="Generate alerts for multiple symbols")
    lp = sub.add_parser("loop", help="Run repeated scans (pure, offline)")
    lp.add_argument("--symbols-json", required=True)
    lp.add_argument("--iterations", type=int, default=2)
    lp.add_argument("--sleep", type=float, default=0.0)

    a.add_argument("--symbols-json", required=True)

    args = p.parse_args(argv)
    if args.cmd == "snapshot":
        return snapshot_main(["--symbol", args.symbol, "--features-json", args.features_json])
    if args.cmd == "scan":
        return scan_main(["--symbols-json", args.symbols_json])
    if args.cmd == "alerts":
        return alerts_main(["--symbols-json", args.symbols_json])
    if args.cmd == "command-room":
        return command_room_main([
            "--symbols-json", args.symbols_json,
            "--width", str(getattr(args, "width", 24)),
            "--top-n", str(getattr(args, "top_n", 1)),
            "--iterations", str(getattr(args, "iterations", 1)),
            "--sleep", str(getattr(args, "sleep", 0.0)),
        ])
    if args.cmd == "loop":
        return loop_main([
            "--symbols-json", args.symbols_json,
            "--iterations", str(args.iterations),
            "--sleep", str(args.sleep),
        ])
    p.error("unknown command")

if __name__ == "__main__":
    raise SystemExit(main())


def loop_cmd(symbols, iterations: int = 2) -> list[dict]:
    from optipanel.runtime.loop import run_once
    out = []
    for _ in range(max(1, int(iterations))):
        out.append(run_once(symbols))
    return out


def loop_main(argv=None):
    import argparse, json, time
    ap = argparse.ArgumentParser(prog="sengoku loop")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between iterations (0 for none)")
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    runs = []
    from optipanel.runtime.loop import run_once
    for _ in range(max(1, int(args.iterations))):
        runs.append(run_once(symbols))
        if args.sleep > 0:
            time.sleep(args.sleep)
    print(json.dumps({"iterations": int(args.iterations), "runs": runs}, indent=2, sort_keys=True))
    return 0


def command_room_cmd(symbols, width: int = 24, top_n: int = 1, iterations: int = 1):
    from optipanel.runtime.loop import run_once
    from optipanel.ui.command_room import render_command_room
    outs = []
    for _ in range(max(1, int(iterations))):
        outs.append(render_command_room(run_once(symbols), width=width, top_n=top_n))
    return "\n---\n".join(outs)


def command_room_main(argv=None):
    import argparse, json, time
    from optipanel.runtime.loop import run_once
    from optipanel.ui.command_room import render_command_room
    ap = argparse.ArgumentParser(prog="sengoku command-room")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--width", type=int, default=24)
    ap.add_argument("--top-n", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=0.0)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    chunks = []
    for i in range(max(1, int(args.iterations))):
        chunks.append(render_command_room(run_once(symbols), width=int(args.width), top_n=int(args.top_n)))
        if args.sleep > 0 and i+1 < int(args.iterations):
            time.sleep(args.sleep)
    print("\n---\n".join(chunks))
    return 0
