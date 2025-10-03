from __future__ import annotations

from typing import Any

from optipanel.engine.aggregate import build_symbol_snapshot


def run_local_scan(symbols_to_features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Build snapshots for multiple symbols and return:
      {
        "results": [snapshot, ...],
        "advice_counts": {"attack":int,"defend":int,"standby":int,...},
        "top": [symbols ranked by score desc]
      }
    Pure, deterministic; no I/O.

    Note: advice_counts will dynamically include any advice types found,
    not just the standard attack/defend/standby.
    """
    results: list[dict[str, Any]] = []
    # Bug #29 FIX: Removed redundant alphabetical sort
    # Dictionary iteration order is deterministic (Python 3.7+), and the final
    # 'top' list is sorted by score anyway, making alphabetical pre-sorting wasteful
    for symbol in symbols_to_features:
        snap = build_symbol_snapshot(symbol, symbols_to_features[symbol])
        results.append(snap)

    # Initialize with expected advice types, but handle any new ones dynamically
    advice_counts = {"attack": 0, "defend": 0, "standby": 0}
    for r in results:
        # Safely get advice field with fallback to "standby" if missing
        advice = r.get("advice", "standby")
        # Use safe increment that handles both known and unknown advice types
        advice_counts[advice] = advice_counts.get(advice, 0) + 1

    # Use safe access to score field with default value of 0
    # Handle None values and type conversion robustly
    def safe_score(x):
        """Safely extract and convert score to float for sorting."""
        score = x.get("score", 0)
        if score is None:
            return 0.0
        try:
            # Try to convert to float (handles int, float, numeric strings)
            return float(score)
        except (TypeError, ValueError):
            # If conversion fails, treat as 0
            return 0.0

    top = [r["symbol"] for r in sorted(results, key=safe_score, reverse=True)]
    return {"results": results, "advice_counts": advice_counts, "top": top}
