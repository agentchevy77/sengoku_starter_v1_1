from optipanel.chips.aggregate import aggregate_chips, compute_sustainment, recon_score
from optipanel.chips.compute import compute_chips_by_tf
from optipanel.chips.prob_tf import (
    compute_probchips_daily,
    compute_probchips_h60,
    compute_probchips_m15,
)
from optipanel.prob.chips import compute_prob_chips

BUNDLE_15 = {
    "last": 104.8,
    "dma20": 102.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.5,
    "rs_strength": 0.25,
    "vwap_diff": 0.011,
    "donchian_pos": 0.82,
    "obv_slope": 0.4,
    "chaikin_ad": 0.35,
    "clv": 0.3,
    "vwap_confluence": 0.55,
}

BUNDLE_60 = {
    "last": 105.0,
    "dma20": 101.0,
    "support": 100.5,
    "resistance": 107.0,
    "rvol": 1.4,
    "rs_strength": 0.28,
    "vwap_diff": 0.01,
    "donchian_pos": 0.76,
}

FALLBACK = {
    "last": 105.2,
    "dma20": 100.5,
    "support": 100.0,
    "resistance": 107.5,
    "rvol": 1.6,
    "rs_strength": 0.3,
    "vwap_diff": 0.012,
    "donchian_pos": 0.85,
    "obv_slope": 0.45,
    "chaikin_ad": 0.38,
    "clv": 0.33,
    "avwap_diff": 0.009,
    "vwap_confluence": 0.62,
}


def test_probchips_m15_matches_canonical():
    expected = compute_prob_chips({"15m": {**FALLBACK, **BUNDLE_15}})["15m"]
    actual = compute_probchips_m15(BUNDLE_15, FALLBACK)
    assert actual == expected


def test_probchips_h60_uses_fallback():
    expected = compute_prob_chips({"60m": {**FALLBACK, **BUNDLE_60}})["60m"]
    actual = compute_probchips_h60(BUNDLE_60, FALLBACK)
    assert actual == expected


def test_probchips_daily_from_features_when_no_bundle():
    expected = compute_prob_chips({"1d": FALLBACK})["1d"]
    actual = compute_probchips_daily(None, FALLBACK)
    assert actual == expected


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


def _score(feats, mode):
    chips = compute_chips_by_tf(feats, mode=mode)
    agg = aggregate_chips(chips)
    return recon_score(agg)


def test_recon_modes_return_valid_and_ordered():
    for mode in ("prob", "micro"):
        bull = _score(BULL, mode)
        bear = _score(BEAR, mode)
        assert isinstance(bull, int) and 0 <= bull <= 100
        assert isinstance(bear, int) and 0 <= bear <= 100
        assert bull > bear


def test_sustainment_ordered():
    bull_chips = compute_chips_by_tf(BULL, mode="prob")
    bear_chips = compute_chips_by_tf(BEAR, mode="prob")
    sustain_bull = compute_sustainment(bull_chips)["sustainability"]
    sustain_bear = compute_sustainment(bear_chips)["sustainability"]
    assert sustain_bull > sustain_bear
