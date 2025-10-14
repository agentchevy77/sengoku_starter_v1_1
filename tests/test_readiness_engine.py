from optipanel.readiness.engine import compute_readiness


def test_readiness_bull_vs_bear():
    bull = {
        "D": {
            "breakout_up_prob": 80,
            "trend_long_prob": 85,
            "bounce_up_prob": 60,
            "breakdown_down_prob": 20,
            "trend_short_prob": 15,
            "rejection_down_prob": 25,
        },
        "H1": {
            "breakout_up_prob": 75,
            "trend_long_prob": 78,
            "bounce_up_prob": 55,
            "breakdown_down_prob": 25,
            "trend_short_prob": 20,
            "rejection_down_prob": 30,
        },
        "M15": {
            "breakout_up_prob": 70,
            "trend_long_prob": 72,
            "bounce_up_prob": 50,
            "breakdown_down_prob": 30,
            "trend_short_prob": 28,
            "rejection_down_prob": 35,
        },
    }
    bear = {
        "D": {
            "breakout_up_prob": 20,
            "trend_long_prob": 15,
            "bounce_up_prob": 25,
            "breakdown_down_prob": 80,
            "trend_short_prob": 85,
            "rejection_down_prob": 60,
        },
        "H1": {
            "breakout_up_prob": 25,
            "trend_long_prob": 20,
            "bounce_up_prob": 30,
            "breakdown_down_prob": 75,
            "trend_short_prob": 78,
            "rejection_down_prob": 55,
        },
        "M15": {
            "breakout_up_prob": 30,
            "trend_long_prob": 28,
            "bounce_up_prob": 35,
            "breakdown_down_prob": 70,
            "trend_short_prob": 72,
            "rejection_down_prob": 50,
        },
    }

    sustain_hi = {"sustainability": 80, "fakeout_risk": 25}
    sustain_lo = {"sustainability": 45, "fakeout_risk": 65}

    r_bull = compute_readiness(bull, sustain_hi, {"long": {"state": "confirmed"}})
    r_bear = compute_readiness(bear, sustain_lo, {"short": {"state": "confirmed"}})

    assert r_bull["attack"] > r_bear["attack"]
    assert r_bear["defense"] > r_bull["defense"]


def test_readiness_acceptance_string_nodes():
    chips = {
        "D": {"breakout_up_prob": 50, "trend_long_prob": 50, "rejection_down_prob": 20},
        "H1": {"breakout_up_prob": 40, "trend_long_prob": 40, "rejection_down_prob": 30},
        "M15": {"breakout_up_prob": 30, "trend_long_prob": 30, "rejection_down_prob": 40},
    }
    sustain = {"sustainability": 55, "fakeout_risk": 45}
    acceptance = {"long": "confirmed", "short": "rejected"}

    readiness = compute_readiness(chips, sustain, acceptance)

    assert readiness["attack"] >= readiness["defense"]
    assert readiness["components"]["accept_bias"]["long"] > 0
    assert readiness["components"]["accept_bias"]["short"] < 0
