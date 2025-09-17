from __future__ import annotations
import argparse, json
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.engine.scan import run_local_scan
from optipanel.alerts.engine import analyze_batch, DEFAULT_THRESH

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
    a.add_argument("--symbols-json", required=True)
    args = p.parse_args(argv)
    if args.cmd == "snapshot":
        return snapshot_main(["--symbol", args.symbol, "--features-json", args.features_json])
    if args.cmd == "scan":
        return scan_main(["--symbols-json", args.symbols_json])
    if args.cmd == "alerts":
        return alerts_main(["--symbols-json", args.symbols_json])
    p.error("unknown command")

if __name__ == "__main__":
    raise SystemExit(main())


def snapshot_cmd(argv=None):
    return snapshot_main(argv)
