from optipanel.readiness import compute_readiness

BULL = {
    "D": {
        "trend_long_prob": 80,
        "breakout_up_prob": 75,
        "bounce_up_prob": 60,
        "trend_short_prob": 20,
        "breakdown_down_prob": 15,
        "rejection_down_prob": 25,
    },
    "H1": {
        "trend_long_prob": 70,
        "breakout_up_prob": 65,
        "bounce_up_prob": 55,
        "trend_short_prob": 30,
        "breakdown_down_prob": 25,
        "rejection_down_prob": 35,
    },
    "M15": {
        "trend_long_prob": 65,
        "breakout_up_prob": 60,
        "bounce_up_prob": 55,
        "trend_short_prob": 35,
        "breakdown_down_prob": 30,
        "rejection_down_prob": 40,
    },
}

BEAR = {
    "D": {
        "trend_long_prob": 20,
        "breakout_up_prob": 15,
        "bounce_up_prob": 25,
        "trend_short_prob": 80,
        "breakdown_down_prob": 75,
        "rejection_down_prob": 60,
    },
    "H1": {
        "trend_long_prob": 30,
        "breakout_up_prob": 25,
        "bounce_up_prob": 35,
        "trend_short_prob": 70,
        "breakdown_down_prob": 65,
        "rejection_down_prob": 55,
    },
    "M15": {
        "trend_long_prob": 35,
        "breakout_up_prob": 30,
        "bounce_up_prob": 40,
        "trend_short_prob": 65,
        "breakdown_down_prob": 60,
        "rejection_down_prob": 50,
    },
}


def test_readiness_bull_vs_bear():
    sustain_bull = {"sustainability": 75, "fakeout_risk": 30}
    sustain_bear = {"sustainability": 35, "fakeout_risk": 70}

    r_bull = compute_readiness(BULL, sustain_bull, acceptance=None)
    r_bear = compute_readiness(BEAR, sustain_bear, acceptance=None)

    assert r_bull["attack"] > r_bull["defense"]
    assert r_bear["defense"] > r_bear["attack"]


def test_acceptance_bias():
    sustain = {"sustainability": 60, "fakeout_risk": 40}
    base = compute_readiness(BULL, sustain, acceptance=None)
    biased = compute_readiness(
        BULL,
        sustain,
        acceptance={"long": {"state": "confirmed"}, "short": {"state": "none"}},
    )
    assert biased["attack"] >= base["attack"] + 8
