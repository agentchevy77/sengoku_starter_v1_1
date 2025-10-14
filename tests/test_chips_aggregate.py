from optipanel.chips.aggregate import aggregate_chips, recon_score


def test_weighted_average_basic():
    chips = {
        "D": {"breakout_up": 80, "trend_long": 70},
        "H1": {"breakout_up": 60, "trend_long": 50},
        "M15": {"breakout_up": 40, "trend_long": 30},
    }
    agg = aggregate_chips(chips, {"D": 0.5, "H1": 0.3, "M15": 0.2})
    assert agg["breakout_up"] == 66
    assert agg["trend_long"] == 56


def test_missing_keys_normalize():
    chips = {
        "D": {"breakout_up": 80},
        "H1": {"breakout_up": 60, "bounce_up": 50},
        "M15": {"bounce_up": 40},
    }
    agg = aggregate_chips(chips, {"D": 0.5, "H1": 0.3, "M15": 0.2})
    expected_bu = round((80 * 0.5 + 60 * 0.3) / 0.8)
    assert agg["breakout_up"] in (expected_bu, expected_bu - 1)
    assert agg["bounce_up"] == 46


def test_recon_score_deterministic_and_clamped():
    agg = {"breakout_up": 90, "trend_long": 80, "rejection_down": 50}
    assert recon_score(agg) == 60
    assert recon_score({"breakout_up": 0, "trend_long": 0, "rejection_down": 100}) == 0
    assert recon_score({"breakout_up": 100, "trend_long": 100, "rejection_down": 0}) == 100
