from optipanel.acceptance.engine import detect_breakout_acceptance


def _bars(*rows):
    bars = []
    for close, low, high, volume in rows:
        bars.append(
            {
                "open": close,
                "close": close,
                "low": low,
                "high": high,
                "volume": volume,
            }
        )
    return bars


def test_acceptance_clean_retest():
    level = 101.0
    bars = _bars(
        (100.5, 100.2, 101.0, 1000),
        (101.4, 101.1, 101.8, 1500),  # breakout
        (101.2, 100.9, 101.5, 900),  # low-volume retest touching level
    )
    res = detect_breakout_acceptance(bars, level)
    assert res["armed"]
    assert res["accepted"]
    assert res["debug"]["direction"] == "up"


def test_reject_high_volume_failure():
    level = 101.0
    bars = _bars(
        (100.5, 100.2, 101.0, 1000),
        (101.4, 101.1, 101.8, 1200),  # breakout
        (100.8, 100.2, 101.0, 1400),  # high-volume flush below level
    )
    res = detect_breakout_acceptance(bars, level)
    assert res["armed"]
    assert not res["accepted"]


def test_range_not_armed():
    level = 101.0
    bars = _bars(
        (100.5, 100.2, 100.8, 1000),
        (100.9, 100.6, 101.0, 900),
        (100.7, 100.4, 100.9, 950),
    )
    res = detect_breakout_acceptance(bars, level)
    assert not res["armed"]
    assert not res["accepted"]


def test_downside_breakout_and_acceptance():
    level = 96.0
    bars = _bars(
        (97.5, 97.0, 97.8, 1200),
        (95.4, 95.1, 97.2, 1500),  # downside breakout
        (95.6, 95.5, 96.2, 1300),  # retest above level but closes back below on lower volume
    )
    res = detect_breakout_acceptance(bars, level)
    assert res["armed"]
    assert res["accepted"]
    assert res["debug"]["direction"] == "down"


def test_no_acceptance_when_retest_volume_high():
    level = 101.0
    bars = _bars(
        (100.5, 100.1, 101.0, 900),
        (101.6, 101.2, 102.1, 1200),  # breakout
        (101.3, 100.9, 101.4, 1300),  # touches but volume not reduced enough
    )
    res = detect_breakout_acceptance(bars, level)
    assert res["armed"]
    assert not res["accepted"]


def test_missing_or_short_series_returns_false():
    assert detect_breakout_acceptance([], 100.0)["armed"] is False
    assert detect_breakout_acceptance(None, 100.0)["armed"] is False
    assert detect_breakout_acceptance(_bars((100.0, 99.5, 100.5, 800)), 100.0)["armed"] is False


def test_acceptance_handles_zero_volumes():
    level = 101.0
    bars = _bars(
        (100.0, 99.5, 101.1, 0),
        (101.5, 101.2, 101.8, 0),
        (101.2, 100.9, 101.3, 0),
    )
    res = detect_breakout_acceptance(bars, level)
    assert res["armed"]
    assert res["accepted"]
