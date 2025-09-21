from optipanel.battlefield.units_v2 import compute_units_v2

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.25,
    "vwap_diff": 0.012,
    "donchian_pos": 0.9,
    "avwap_diff": 0.02,
    "obv_slope": 0.7,
    "chaikin_ad": 0.55,
    "clv": 0.6,
    "vwap_confluence": 0.6,
}

BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 99.0,
    "rvol": 0.85,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
    "donchian_pos": 0.1,
    "avwap_diff": -0.02,
    "obv_slope": -0.7,
    "chaikin_ad": -0.5,
    "clv": -0.6,
    "vwap_confluence": 0.4,
}


KEYS = ("dma20", "support", "resistance", "rvol", "rs", "donchian", "obv", "ad", "clv", "avwap")


def test_units_present_and_directional():
    bull_units = compute_units_v2(BULL)
    bear_units = compute_units_v2(BEAR)

    for units in (bull_units, bear_units):
        for key in KEYS:
            assert key in units
            assert set(units[key]) == {"bull", "bear"}
            assert 0 <= units[key]["bull"] <= 100
            assert units[key]["bull"] + units[key]["bear"] == 100

    assert bull_units["dma20"]["bull"] > bear_units["dma20"]["bull"]
    assert bull_units["support"]["bull"] > bear_units["support"]["bull"]
    assert bull_units["resistance"]["bull"] < bear_units["resistance"]["bull"]
    assert bull_units["rvol"]["bull"] > bear_units["rvol"]["bull"]
    assert bull_units["rs"]["bull"] > bear_units["rs"]["bull"]
    assert bull_units["donchian"]["bull"] > bear_units["donchian"]["bull"]
    assert bull_units["obv"]["bull"] > bear_units["obv"]["bull"]
    assert bull_units["ad"]["bull"] > bear_units["ad"]["bull"]
    assert bull_units["clv"]["bull"] > bear_units["clv"]["bull"]
    assert bull_units["avwap"]["bull"] > bear_units["avwap"]["bull"]


def test_defaults_return_neutral_units():
    neutral = compute_units_v2({})
    for key in KEYS:
        assert neutral[key]["bull"] == 50
        assert neutral[key]["bear"] == 50
