from optipanel.engine.aggregate import build_symbol_snapshot

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


def _check_snapshot(s):
    assert isinstance(s, dict)
    assert "symbol" in s and isinstance(s["symbol"], str)
    assert "units" in s and isinstance(s["units"], dict)
    assert "setups" in s and isinstance(s["setups"], dict)
    assert "score" in s and isinstance(s["score"], int) and 0 <= s["score"] <= 100
    assert "advice" in s and s["advice"] in ("attack", "defend", "standby")


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
