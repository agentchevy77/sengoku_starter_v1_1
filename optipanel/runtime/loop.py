from __future__ import annotations
from typing import Dict, Any, List

from optipanel.engine.scan import run_local_scan
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.alerts.engine import analyze_batch, DEFAULT_THRESH

def run_once(symbols_to_features: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    One pure "tick":
      - scan (ranking + advice counts)
      - alerts (thresholded signals)
    No sleeping, no I/O, no network.
    """
    # Scan first (ranks + advice)
    scan_out = run_local_scan(symbols_to_features)

    # Build fresh snapshots for alerts (keeps function boundaries clean)
    snaps = [
        build_symbol_snapshot(sym, feats)
        for sym, feats in symbols_to_features.items()
    ]
    alerts_out = analyze_batch(snaps, DEFAULT_THRESH)

    return {"scan": scan_out, "alerts": alerts_out}


def run_once_with(provider, symbols):
    """Use a FeaturesProvider to collect features, then run the pure tick."""
    feats = provider.features_for_symbols(list(symbols))
    return run_once(feats)
