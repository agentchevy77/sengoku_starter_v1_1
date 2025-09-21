from optipanel.chips.aggregate import aggregate_chips, recon_score


def test_aggregate_chips_weighted_average():
    chips = {
        "D": {"breakout_up_prob": 80, "trend_long_prob": 70},
        "H1": {"breakout_up_prob": 60, "trend_long_prob": 50, "fakeout_risk_prob": 20},
        "M15": {"trend_long_prob": 40},
    }
    weights = {"D": 2.0, "H1": 1.0}

    out = aggregate_chips(chips, weights)
    assert out["breakout_up_prob"] == 73  # (80*2 + 60*1) / 3
    assert out["trend_long_prob"] == 58  # (70*2 + 50*1 + 40*1) / 4
    assert out["fakeout_risk_prob"] == 20


def test_aggregate_chips_handles_missing_and_clamps():
    chips = {
        "D": {"breakout_up_prob": 120},
        "H1": {"breakout_up_prob": -20},
    }
    out = aggregate_chips(chips)
    assert out["breakout_up_prob"] == 50  # simple mean with equal weights

    assert aggregate_chips({}) == {}


def test_recon_score():
    data = {
        "breakout_up_prob": 80,
        "trend_long_prob": 70,
        "rejection_down_prob": 30,
    }
    assert recon_score(data) == 60

    assert recon_score({}) == 0

    data_missing = {"breakout_up": 90, "trend_long": 60}
    assert recon_score(data_missing) == 75

    negative = {"rejection_down": 80}
    assert recon_score(negative) == 0
