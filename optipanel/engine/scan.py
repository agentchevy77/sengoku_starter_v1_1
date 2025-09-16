from __future__ import annotations
from typing import Dict, Any, List
from optipanel.engine.aggregate import build_symbol_snapshot

def run_local_scan(symbols_to_features: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for symbol in sorted(symbols_to_features.keys()):
        snap = build_symbol_snapshot(symbol, symbols_to_features[symbol])
        results.append(snap)
    advice_counts = {"attack": 0, "defend": 0, "standby": 0}
    for r in results:
        advice_counts[r["advice"]] = advice_counts.get(r["advice"], 0) + 1
    top = [r["symbol"] for r in sorted(results, key=lambda x: x["score"], reverse=True)]
    return {"results": results, "advice_counts": advice_counts, "top": top}
