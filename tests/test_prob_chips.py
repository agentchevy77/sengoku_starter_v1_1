import math

from optipanel.chips.daily import compute_daily_microchips
from optipanel.chips.h60 import compute_h60_microchips
from optipanel.chips.m15 import compute_m15_microchips
from optipanel.prob.chips import compute_prob_chips

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.25,
    "vwap_diff": 0.015,
    "donchian_pos": 0.92,
    "avwap_diff": 0.025,
    "obv_slope": 0.7,
    "chaikin_ad": 0.6,
    "clv": 0.55,
    "vwap_confluence": 0.7,
}

BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 0.85,
    "rs_strength": -0.28,
    "vwap_diff": -0.02,
    "donchian_pos": 0.08,
    "avwap_diff": -0.03,
    "obv_slope": -0.65,
    "chaikin_ad": -0.6,
    "clv": -0.55,
    "vwap_confluence": 0.4,
}


def _check_chip_block(block):
    keys = {
        "breakout_up",
        "breakdown_down",
        "bounce_up",
        "rejection_down",
        "trend_long",
        "trend_short",
        "fakeout",
    }
    assert set(block.keys()) == keys
    for value in block.values():
        assert isinstance(value, int)
        assert 0 <= value <= 100


def test_prob_chips_keys_and_summary():
    bundles = {"15m": BULL, "60m": BEAR}
    chips = compute_prob_chips(bundles)
    assert set(chips.keys()) == {"15m", "60m", "summary"}
    _check_chip_block(chips["15m"])
    _check_chip_block(chips["60m"])
    _check_chip_block(chips["summary"])
    for key in chips["summary"]:
        assert chips["summary"][key] == int(round((chips["15m"][key] + chips["60m"][key]) / 2))


def test_prob_chips_directionality():
    bull = compute_prob_chips({"15m": BULL})["15m"]
    bear = compute_prob_chips({"15m": BEAR})["15m"]
    assert bull["breakout_up"] > bear["breakout_up"]
    assert bull["trend_long"] > bear["trend_long"]
    assert bull["bounce_up"] > bear["bounce_up"]
    assert bear["breakdown_down"] > bull["breakdown_down"]
    assert bear["trend_short"] > bull["trend_short"]
    assert bear["rejection_down"] > bull["rejection_down"]
    assert 0 <= bull["fakeout"] <= 100
    assert 0 <= bear["fakeout"] <= 100


def test_prob_chips_handles_empty():
    assert compute_prob_chips({}) == {}
    assert compute_prob_chips(None) == {}


def test_prob_chips_faulty_values():
    noisy_bundle = {
        "last": math.nan,
        "dma20": float("inf"),
        "support": 100.0,
        "resistance": 106.0,
        "rvol": "1.4",
        "rs_strength": None,
        "vwap_diff": "-0.01",
        "donchian_pos": "0.72",
        "avwap_diff": None,
        "obv_slope": math.nan,
        "chaikin_ad": "0.3",
        "clv": "oops",
        "vwap_confluence": None,
    }

    chips = compute_prob_chips({"15m": noisy_bundle})
    assert set(chips.keys()) == {"15m", "summary"}
    for block in chips.values():
        for val in block.values():
            assert isinstance(val, int)
            assert 0 <= val <= 100


def test_compute_m15_microchips_keys():
    micro = compute_m15_microchips(BULL)
    expected = {
        "donchian",
        "trend_dma",
        "support_def",
        "res_clear",
        "rvol",
        "rs",
        "vwap",
    }
    assert expected.issubset(micro)
    for value in micro.values():
        assert isinstance(value, int)


def test_compute_h60_microchips_keys():
    micro = compute_h60_microchips(BULL)
    expected = {
        "donchian",
        "trend_dma",
        "support_def",
        "res_clear",
        "rvol",
        "rs",
        "vwap",
    }
    assert expected.issubset(micro)
    for value in micro.values():
        assert isinstance(value, int)


def test_compute_daily_microchips_keys():
    micro = compute_daily_microchips(BULL)
    expected = {
        "donchian",
        "trend_dma",
        "support_def",
        "res_clear",
        "rvol",
        "rs",
        "vwap",
    }
    assert expected.issubset(micro)
    for value in micro.values():
        assert isinstance(value, int)
