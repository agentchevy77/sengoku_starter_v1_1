from __future__ import annotations

from optipanel.recon.enrich import build_recon_entry

FEATURES = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
    "bundles": {
        "15m": {"last": 104.5, "dma20": 101.0, "support": 100.2, "resistance": 105.5, "rvol": 1.3, "rs_strength": 0.18},
        "60m": {"last": 104.2, "dma20": 102.0, "support": 101.0, "resistance": 105.8, "rvol": 1.2, "rs_strength": 0.15},
    },
}


def test_build_recon_entry_baseline():
    entry = build_recon_entry(FEATURES)
    assert entry["recon"]
    assert "agg" in entry and "tf" in entry
    assert "sustainment" in entry and "supply" not in entry
    assert "tf_scout" not in entry


def test_build_recon_entry_with_supply_and_summary():
    entry = build_recon_entry(FEATURES, include_supply=True, include_summary=True)
    assert entry["supply"]
    assert entry["chips_summary"]
    sustain = entry["sustainment"]
    assert sustain["sustainability"] >= 0 and sustain["fakeout_risk"] >= 0


def test_build_recon_entry_micro_mode_still_prob_canonical():
    entry = build_recon_entry(FEATURES, mode="micro")
    assert entry["tf"]
    assert entry.get("tf_scout")
    assert entry["recon"] > 0
