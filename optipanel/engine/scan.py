from __future__ import annotations

from typing import Any

from optipanel.engine.aggregate import build_symbol_snapshot


def run_local_scan(symbols_to_features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Build snapshots for multiple symbols and return:
      {
        "results": [snapshot, ...],
        "advice_counts": {"attack":int,"defend":int,"standby":int},
        "top": [symbols ranked by score desc]
      }
    Pure, deterministic; no I/O.
    """
    results: list[dict[str, Any]] = []
    for symbol in sorted(symbols_to_features.keys()):
        snap = build_symbol_snapshot(symbol, symbols_to_features[symbol])
        results.append(snap)

    advice_counts = {"attack": 0, "defend": 0, "standby": 0}
    for r in results:
        advice_counts[r["advice"]] = advice_counts.get(r["advice"], 0) + 1

    top = [r["symbol"] for r in sorted(results, key=lambda x: x["score"], reverse=True)]
    return {"results": results, "advice_counts": advice_counts, "top": top}
