import math
import os

import pytest

from optipanel.probs import coerce_features, compute_chips
from optipanel.probs.spec import DEFAULTS

BULL = {
    "last": 305.4,
    "dma20": 301.2,
    "support": 299.5,
    "resistance": 308.1,
    "rvol": 1.35,
    "rs_strength": 0.22,
    "vwap_diff": 0.008,
    "donchian_pos": 0.88,
    "avwap_diff": 0.016,
    "obv_slope": 0.60,
    "chaikin_ad": 0.55,
    "clv": 0.49,
    "vwap_confluence": 0.68,
}

BEAR = {
    "last": 92.8,
    "dma20": 96.4,
    "support": 91.5,
    "resistance": 97.2,
    "rvol": 0.82,
    "rs_strength": -0.18,
    "vwap_diff": -0.009,
    "donchian_pos": 0.20,
    "avwap_diff": -0.013,
    "obv_slope": -0.44,
    "chaikin_ad": -0.41,
    "clv": -0.37,
    "vwap_confluence": 0.36,
}


def _assert_chip_block(chips):
    expected_keys = {
        "breakout_up_prob",
        "breakdown_down_prob",
        "bounce_up_prob",
        "rejection_down_prob",
        "trend_long_prob",
        "trend_short_prob",
        "sustainment_prob",
        "fakeout_risk_prob",
    }
    assert set(chips.keys()) == expected_keys
    for value in chips.values():
        assert isinstance(value, int)
        assert 0 <= value <= 100


@pytest.mark.parametrize("timeframe", ["15m", "60m", "1d"])
def test_prob_chips_directional(timeframe):
    bull = compute_chips(BULL, timeframe)
    bear = compute_chips(BEAR, timeframe)
    _assert_chip_block(bull)
    _assert_chip_block(bear)

    assert bull["breakout_up_prob"] > bear["breakout_up_prob"]
    assert bear["breakdown_down_prob"] > bull["breakdown_down_prob"]
    assert bull["trend_long_prob"] > bear["trend_long_prob"]
    assert bear["trend_short_prob"] > bull["trend_short_prob"]
    assert bull["sustainment_prob"] >= bear["sustainment_prob"]


def test_compute_chips_invalid_timeframe():
    with pytest.raises(ValueError):
        compute_chips(BULL, "2h")


def test_compute_chips_5m_disabled(monkeypatch):
    monkeypatch.delenv("SENGOKU_CHIPS_5M", raising=False)
    with pytest.raises(ValueError):
        compute_chips(BULL, "5m")


def test_compute_chips_5m_flag(monkeypatch):
    monkeypatch.setenv("SENGOKU_CHIPS_5M", "1")
    chips = compute_chips(BULL, "5m")
    _assert_chip_block(chips)
    monkeypatch.delenv("SENGOKU_CHIPS_5M", raising=False)


def test_compute_chips_handles_missing_values():
    minimal = {"last": 100.0}
    chips = compute_chips(minimal, "15m")
    _assert_chip_block(chips)


def test_compute_chips_handles_nan_and_strings():
    noisy = {
        "last": 210.0,
        "dma20": 208.0,
        "support": 205.0,
        "resistance": 212.0,
        "rvol": "1.3",
        "rs_strength": None,
        "vwap_diff": "-0.012",
        "donchian_pos": "0.7",
        "avwap_diff": math.nan,
        "obv_slope": float("inf"),
        "chaikin_ad": "0.4",
        "clv": "oops",
        "vwap_confluence": None,
    }
    chips = compute_chips(noisy, "60m")
    _assert_chip_block(chips)


def test_coerce_features_provides_all_defaults():
    bundle = coerce_features({"last": 10.0})
    for key in DEFAULTS:
        assert key in bundle


def _range(d, keys):
    for k in keys:
        assert k in d, f"missing {k}"
        assert isinstance(d[k], int)
        assert 0 <= d[k] <= 100


def test_bullish_60m_profile():
    chips = compute_chips(BULL, "60m")
    _range(
        chips,
        (
            "breakout_up_prob",
            "trend_long_prob",
            "sustainment_prob",
            "fakeout_risk_prob",
            "breakdown_down_prob",
            "rejection_down_prob",
            "bounce_up_prob",
            "trend_short_prob",
        ),
    )
    assert chips["breakout_up_prob"] >= 70
    assert chips["trend_long_prob"] >= 70
    assert chips["breakdown_down_prob"] <= 40
    assert chips["rejection_down_prob"] <= 55
    assert chips["sustainment_prob"] >= 60
    assert chips["fakeout_risk_prob"] <= 50


def test_bearish_60m_profile():
    bear = compute_chips(BEAR, "60m")
    bull = compute_chips(BULL, "60m")

    assert bear["breakdown_down_prob"] >= bull["breakdown_down_prob"]
    assert bear["trend_short_prob"] >= 80
    assert bear["breakout_up_prob"] <= bull["breakout_up_prob"]
    assert bear["bounce_up_prob"] <= bull["bounce_up_prob"]
    assert bear["sustainment_prob"] <= bull["sustainment_prob"]
    assert bear["fakeout_risk_prob"] >= bull["fakeout_risk_prob"]


def test_15m_is_more_sensitive_than_1d_on_same_bundle():
    chips_15 = compute_chips(BULL, "15m")
    chips_1d = compute_chips(BULL, "1d")
    assert chips_15["breakout_up_prob"] >= chips_1d["breakout_up_prob"] - 5
    assert chips_15["trend_long_prob"] >= chips_1d["trend_long_prob"] - 5


def test_5m_is_gated_by_flag(monkeypatch):
    if os.getenv("SENGOKU_CHIPS_5M") == "1":
        pytest.skip("Flag enabled in env; skip gate test.")
    with pytest.raises(ValueError):
        compute_chips(BULL, "5m")
