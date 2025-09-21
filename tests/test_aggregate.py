import math

import pytest

from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.prob.chips import compute_prob_chips

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}

BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 1.5,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
}


def test_aggregate_with_timeframe_bundles():
    bundles = {
        "15m": {
            "last": 104.2,
            "dma20": 103.8,
            "support": 102.6,
            "resistance": 105.1,
            "rvol": 1.3,
            "rs_strength": 0.18,
            "vwap_diff": 0.009,
            "donchian_pos": 0.86,
            "obv_slope": 0.55,
            "chaikin_ad": 0.48,
            "clv": 0.42,
            "avwap_diff": 0.014,
            "vwap_confluence": 0.62,
        },
        "60m": {
            "last": 103.9,
            "dma20": 103.2,
            "support": 102.0,
            "resistance": 105.5,
            "rvol": 1.1,
            "rs_strength": 0.12,
            "vwap_diff": 0.006,
            "donchian_pos": 0.74,
            "obv_slope": 0.41,
            "chaikin_ad": 0.35,
            "clv": 0.38,
            "avwap_diff": 0.010,
            "vwap_confluence": 0.54,
        },
        "1d": {
            "last": 105.0,
            "dma20": 100.0,
            "support": 101.0,
            "resistance": 106.0,
            "rvol": 1.6,
            "rs_strength": 0.30,
            "vwap_diff": 0.012,
            "donchian_pos": 0.92,
            "obv_slope": 0.68,
            "chaikin_ad": 0.57,
            "clv": 0.51,
            "avwap_diff": 0.021,
            "vwap_confluence": 0.70,
        },
    }
    features = {"bundles": bundles, **BULL}
    snap = build_symbol_snapshot("TEST", features)
    chips = snap["prob_chips"]
    assert {"1d", "60m", "15m", "summary"}.issubset(chips.keys())
    assert snap["battlefield_bundle"]["last"] == pytest.approx(bundles["1d"]["last"])
    expected = compute_prob_chips(dict(bundles.items()))
    assert chips == expected


def test_aggregate_faulty_bundles():
    features = {
        "last": 110.0,
        "dma20": 105.0,
        "support": 104.0,
        "resistance": 112.0,
        "rvol": 1.2,
        "rs_strength": 0.15,
        "vwap_diff": 0.01,
        "bundles": {
            "15m": {
                "last": math.nan,
                "dma20": "bad",
                "support": 108.0,
                "resistance": 111.0,
                "rvol": "1.3",
            },
            "gibberish": "text",
            "60m": {
                "last": 108.5,
                "dma20": 107.2,
                "support": 106.5,
                "resistance": float("inf"),
                "rvol": 1.1,
                "rs_strength": 0.12,
                "vwap_diff": 0.007,
                "donchian_pos": 0.74,
            },
        },
    }

    snap = build_symbol_snapshot("MAL", features)
    assert snap["symbol"] == "MAL"
    assert snap["prob_chips"]
    for block in snap["prob_chips"].values():
        assert isinstance(block, dict)
        for val in block.values():
            assert isinstance(val, int)
            assert 0 <= val <= 100
    # bundle should fall back to 60m values without NaNs/inf
    bundle = snap["battlefield_bundle"]
    assert bundle["last"] == pytest.approx(108.5)
    if "resistance" in bundle:
        assert bundle["resistance"] <= 500.0


def _check_snapshot(s):
    assert isinstance(s, dict)
    assert "symbol" in s and isinstance(s["symbol"], str)
    assert "units" in s and isinstance(s["units"], dict)
    assert "setups" in s and isinstance(s["setups"], dict)
    assert "score" in s and isinstance(s["score"], int) and 0 <= s["score"] <= 100
    assert "advice" in s and s["advice"] in ("attack", "defend", "standby")
    assert "battlefield_bundle" in s and isinstance(s["battlefield_bundle"], dict)
    assert "prob_chips" in s and isinstance(s["prob_chips"], dict)
    chips = s["prob_chips"]
    assert "summary" in chips
    for block in chips.values():
        assert isinstance(block, dict)


def test_aggregate_bullish():
    snap = build_symbol_snapshot("TEST", BULL)
    _check_snapshot(snap)
    assert snap["score"] >= 60
    assert snap["advice"] in ("attack", "standby")


def test_aggregate_bearish():
    snap = build_symbol_snapshot("TEST", BEAR)
    _check_snapshot(snap)
    assert snap["score"] <= 40
    assert snap["advice"] in ("defend", "standby")
