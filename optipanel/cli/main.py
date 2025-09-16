from __future__ import annotations
from typing import Dict, Any
from optipanel.engine.aggregate import build_symbol_snapshot

# Pure function used by tests
def snapshot_cmd(symbol: str, features: Dict[str, Any]) -> Dict[str, Any]:
    return build_symbol_snapshot(symbol, features)

# Optional: small CLI for manual demos
def main(argv=None):
    import argparse, json
    p = argparse.ArgumentParser(prog="sengoku")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="Print snapshot JSON")
    s.add_argument("--symbol", required=True)
    s.add_argument("--features-json", required=True, help="JSON dict of features")
    args = p.parse_args(argv)

    if args.cmd == "snapshot":
        try:
            features = json.loads(args.features_json)
            if not isinstance(features, dict):
                raise ValueError("features-json must be a JSON object")
        except Exception as e:
            p.error(f"Invalid --features-json: {e}")
        snap = snapshot_cmd(args.symbol, features)
        print(json.dumps(snap, indent=2, sort_keys=True))
        return 0

    p.error("unknown command")

if __name__ == "__main__":
    raise SystemExit(main())
