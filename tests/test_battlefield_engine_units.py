from __future__ import annotations

import math

from optipanel.battlefield.engine import compute_units


def test_compute_units_bullish_bias_and_near_levels():
    features = {
        "last": 102.0,
        "dma20": "100.0",  # exercise coercion
        "support": 101.5,
        "resistance": 102.7,
        "rvol": 1.35,
        "rs_strength": 0.2,
    }

    units = compute_units(features)

    assert units["dma20"] == {"bull": 70, "bear": 30}
    assert units["support"] == {"bull": 75, "bear": 25}
    assert units["resistance"] == {"bull": 25, "bear": 75}
    assert units["rvol"] == {"bull": 60, "bear": 40}
    assert units["rs"] == {"bull": 60, "bear": 40}


def test_compute_units_bearish_bias_and_resistance_break():
    features = {
        "last": 95.0,
        "dma20": 100.0,
        "support": 101.0,
        "resistance": 93.0,
        "rvol": 0.7,
        "rs_strength": -0.25,
    }

    units = compute_units(features)

    assert units["dma20"] == {"bull": 30, "bear": 70}
    assert units["support"] == {"bull": 25, "bear": 75}
    assert units["resistance"] == {"bull": 65, "bear": 35}
    assert units["rvol"] == {"bull": 40, "bear": 60}
    assert units["rs"] == {"bull": 40, "bear": 60}


def test_compute_units_neutral_when_data_missing_or_invalid():
    features = {
        "last": "not-a-number",
        "support": None,
        "rvol": "oops",
    }

    units = compute_units(features)

    for key in ("dma20", "support", "resistance", "rvol", "rs"):
        assert units[key] == {"bull": 50, "bear": 50}


def test_compute_units_support_and_resistance_far_from_price_remain_neutral():
    features = {
        "last": 120.0,
        "dma20": 119.0,
        "support": 100.0,
        "resistance": 150.0,
    }

    units = compute_units(features)

    # dma20 still bull because last >= dma20
    assert units["dma20"] == {"bull": 70, "bear": 30}
    # support/resistance should remain neutral because levels are far away
    assert units["support"] == {"bull": 50, "bear": 50}
    assert units["resistance"] == {"bull": 50, "bear": 50}


def test_compute_units_avoids_division_by_zero():
    features = {
        "last": 0.0,
        "support": 0.0,
        "resistance": 0.0,
    }

    units = compute_units(features)

    # When last == 0 we should keep neutral weights and not crash
    assert units["support"] == {"bull": 50, "bear": 50}
    assert units["resistance"] == {"bull": 50, "bear": 50}
    # ensure computation executed without NaN/Inf side-effects
    for weights in units.values():
        assert all(not math.isnan(v) for v in weights.values())
