from __future__ import annotations

from typing import Any

from optipanel.alerts.engine import DEFAULT_THRESH, analyze_batch
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.engine.scan import run_local_scan


def run_once(symbols_to_features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    One pure "tick":
      - scan (ranking + advice counts)
      - alerts (thresholded signals)
    No sleeping, no I/O, no network.
    """
    # Scan first (ranks + advice)
    scan_out = run_local_scan(symbols_to_features)

    # Build fresh snapshots for alerts (keeps function boundaries clean)
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols_to_features.items()]
    alerts_out = analyze_batch(snaps, DEFAULT_THRESH)

    out: dict[str, Any] = {"scan": scan_out, "alerts": alerts_out}

    top_list = scan_out.get("top") if isinstance(scan_out, dict) else None
    # Fixed: Proper bounds check for empty list
    top_sym = top_list[0] if (top_list and len(top_list) > 0) else None
    if top_sym:
        features_top = symbols_to_features.get(top_sym)
        if isinstance(features_top, dict):
            out.setdefault("panels", {})["features_top"] = dict(features_top)

    return out


def run_once_with(provider, symbols):
    """Use a FeaturesProvider to collect features, then run the pure tick."""
    feats = provider.features_for_symbols(list(symbols))
    return run_once(feats)
