from __future__ import annotations

from optipanel.chips.lib import microchips_from_features, probs_from_microchips


def test_microchips_from_features_delegates(monkeypatch):
    captured = {}

    def fake_compute(features):
        captured["features"] = features
        return {"trend_dma": 80}

    monkeypatch.setattr("optipanel.chips.lib.compute_microchips_m15", fake_compute)
    features = {"last": 105.0}
    result = microchips_from_features(features)
    assert result == {"trend_dma": 80}
    assert captured["features"] == features


def test_probs_from_microchips_conversion():
    micro = {
        "donchian": 70,
        "trend_dma": 75,
        "support_def": 60,
        "res_clear": 65,
        "rvol": 80,
        "rs": 55,
        "vwap": 60,
    }
    result = probs_from_microchips(micro)
    assert result == {
        "breakout_up_prob": 68,
        "breakdown_down_prob": 46,
        "bounce_up_prob": 54,
        "rejection_down_prob": 40,
        "trend_long_prob": 69,
        "trend_short_prob": 34,
        "exhaustion_prob": 73,
    }
