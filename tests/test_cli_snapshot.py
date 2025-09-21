from optipanel.cli.main import snapshot_cmd

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


def _check(s):
    assert isinstance(s, dict)
    for k in ("symbol", "units", "setups", "score", "advice", "battlefield_bundle", "prob_chips"):
        assert k in s
    assert 0 <= s["score"] <= 100
    assert s["advice"] in ("attack", "defend", "standby")


def test_cli_snapshot_bullish():
    snap = snapshot_cmd("TEST", BULL)
    _check(snap)
    assert snap["score"] >= 60
    assert snap["advice"] in ("attack", "standby")


def test_cli_snapshot_bearish():
    snap = snapshot_cmd("TEST", BEAR)
    _check(snap)
    assert snap["score"] <= 40
    assert snap["advice"] in ("defend", "standby")
