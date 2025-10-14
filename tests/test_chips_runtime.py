from __future__ import annotations

from optipanel.chips.runtime import chips_by_tf_for_snapshot, supply_for_snapshot
from optipanel.engine.aggregate import build_symbol_snapshot

FEATURES = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
    "bundles": {
        "15m": {
            "last": 104.5,
            "dma20": 101.0,
            "support": 100.2,
            "resistance": 105.5,
            "rvol": 1.3,
            "rs_strength": 0.18,
            "vwap_diff": 0.005,
        },
        "60m": {
            "last": 104.8,
            "dma20": 103.0,
            "support": 102.5,
            "resistance": 105.8,
        },  # missing rvol, rs_strength, etc.
        "1d": {
            "last": 105.0,
            "dma20": 100.0,
            "support": 101.0,
            "resistance": 106.0,
            "rvol": 1.6,
            "rs_strength": 0.30,
            "vwap_diff": 0.012,
        },
    },
}


def test_chips_by_snapshot_handles_malformed_bundles():
    snap = build_symbol_snapshot("AAA", FEATURES)
    chips = chips_by_tf_for_snapshot(snap)
    assert "D" in chips
    assert "H1" in chips
    assert "M15" in chips
    assert chips["D"]  # daily chips present
    assert chips["H1"]  # fallback to daily features if bundle missing fields


def test_supply_for_snapshot_returns_keys():
    features = {
        "last": 105.0,
        "dma20": 100.0,
        "support": 101.0,
        "resistance": 106.0,
        "rvol": 1.6,
        "rs_strength": 0.30,
        "vwap_diff": 0.012,
        "bars": [
            {"open": 100.5, "high": 101.1, "low": 100.2, "close": 100.9, "volume": 900},
            {"open": 101.0, "high": 106.2, "low": 101.0, "close": 105.8, "volume": 1500},
        ],
        "bundles": {
            "15m": {
                "last": 104.5,
                "dma20": 101.0,
                "support": 100.2,
                "resistance": 105.5,
                "rvol": 1.3,
                "rs_strength": 0.18,
            },
            "60m": {
                "last": 104.8,
                "dma20": 103.0,
                "support": 102.5,
                "resistance": 105.8,
                "rvol": 1.1,
                "rs_strength": 0.12,
            },
            "1d": {
                "last": 105.0,
                "dma20": 100.0,
                "support": 101.0,
                "resistance": 106.0,
                "rvol": 1.6,
                "rs_strength": 0.30,
            },
        },
    }
    snap = build_symbol_snapshot("AAA", features)
    supply = supply_for_snapshot(snap)
    assert set(supply.keys()) == {
        "breakout_up",
        "breakdown_down",
        "bounce_up",
        "rejection_down",
        "trend_long",
        "trend_short",
        "exhaustion",
    }
