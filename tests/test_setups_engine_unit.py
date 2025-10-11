"""
Unit tests for optipanel.setups.engine.
Ensures the core setup scoring logic remains stable.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from optipanel.setups.engine import SetupConfig, _as_decimal, compute_setups
from optipanel.utils.decimal_types import D_ONE, D_ZERO

# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def default_config() -> SetupConfig:
    return SetupConfig()


@pytest.fixture
def base_features() -> dict[str, float]:
    """Neutral feature bundle used as a starting point for scenarios."""
    return {
        "last": 100.0,
        "dma20": 100.0,
        "support": 90.0,
        "resistance": 110.0,
        "rvol": 1.0,
        "rs_strength": 0.0,
        "vwap_diff": 0.0,
    }


# --------------------------------------------------------------------------- SetupConfig


def test_setup_config_defaults_are_numeric(default_config: SetupConfig) -> None:
    for attr, value in default_config.__dict__.items():
        assert isinstance(
            value,
            (int, float, Decimal),
        ), f"SetupConfig attribute {attr!r} should be numeric, got {type(value)!r}"


# --------------------------------------------------------------------------- _as_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, D_ZERO),
        ("123.45", Decimal("123.45")),
        (123, Decimal("123")),
        (1.5, Decimal("1.5")),
    ],
)
def test_as_decimal_converts_values(value: object, expected: Decimal) -> None:
    assert _as_decimal(value) == expected


def test_as_decimal_falls_back_on_invalid() -> None:
    result = _as_decimal(object(), default=D_ONE)
    assert result == D_ONE


# --------------------------------------------------------------------------- compute_setups – breakout/breakdown


def test_compute_setups_breakout_dominates(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 115.0,
            "rvol": 2.5,
            "rs_strength": 0.8,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["breakout_up"] == 100
    assert scores["breakdown_down"] < 50
    assert scores["trend_long"] >= 90
    assert scores["exhaustion"] >= 90  # extension + elevated momentum


def test_compute_setups_breakdown_dominates(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 85.0,
            "rvol": 1.5,
            "rs_strength": -0.8,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["breakdown_down"] == 100
    assert scores["breakout_up"] < 50
    assert scores["trend_short"] >= 90
    assert scores["exhaustion"] >= 90  # large extension below dma20


# --------------------------------------------------------------------------- compute_setups – trend continuation


def test_compute_setups_strong_uptrend(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 120.0,
            "dma20": 100.0,
            "rvol": 1.5,
            "rs_strength": 0.9,
            "vwap_diff": 0.05,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["trend_long"] >= 90
    assert scores["trend_short"] <= 35


def test_compute_setups_strong_downtrend(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 80.0,
            "dma20": 100.0,
            "rvol": 1.5,
            "rs_strength": -0.9,
            "vwap_diff": -0.05,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["trend_short"] >= 90
    assert scores["trend_long"] <= 35


# --------------------------------------------------------------------------- compute_setups – bounce / rejection / exhaustion


def test_compute_setups_bounce_up_near_support(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 90.2,
            "dma20": 92.0,
            "rvol": 1.1,
            "rs_strength": 0.3,
            "vwap_diff": 0.01,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["bounce_up"] >= 70
    assert scores["breakdown_down"] >= 80  # still at risk of breaking


def test_compute_setups_rejection_down_near_resistance(
    base_features: dict[str, float],
    default_config: SetupConfig,
) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 109.5,
            "dma20": 105.0,
            "rvol": 1.2,
            "rs_strength": -0.2,
            "vwap_diff": -0.01,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["rejection_down"] >= 65
    assert scores["breakout_up"] > scores["rejection_down"]  # still leaning bullish overall


def test_compute_setups_exhaustion_spikes(base_features: dict[str, float], default_config: SetupConfig) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 150.0,
            "dma20": 100.0,
            "rvol": 1.6,
        }
    )

    scores = compute_setups(features, default_config)

    assert scores["exhaustion"] >= 85
    assert scores["trend_long"] >= 80  # still elevated trend signal


# --------------------------------------------------------------------------- compute_setups – robustness


def test_compute_setups_handles_missing_fields(default_config: SetupConfig) -> None:
    scores = compute_setups({}, default_config)
    expected_keys = {
        "breakout_up",
        "breakdown_down",
        "bounce_up",
        "rejection_down",
        "trend_long",
        "trend_short",
        "exhaustion",
    }
    assert set(scores) == expected_keys
    for value in scores.values():
        assert 0 <= value <= 100


def test_compute_setups_extreme_prices_are_clamped(base_features: dict[str, float]) -> None:
    features = deepcopy(base_features)
    features.update(
        {
            "last": 1e12,
            "dma20": 1e11,
            "support": 1e11,
            "resistance": 1.1e12,
            "rvol": 10.0,
            "rs_strength": 5.0,
        }
    )

    scores = compute_setups(features)
    for value in scores.values():
        assert 0 <= value <= 100


def test_compute_setups_zero_price_is_safe(default_config: SetupConfig) -> None:
    features = {
        "last": 0.0,
        "dma20": 0.0,
        "support": 0.0,
        "resistance": 0.0,
        "rvol": 0.0,
        "rs_strength": 0.0,
        "vwap_diff": 0.0,
    }

    scores = compute_setups(features, default_config)
    for value in scores.values():
        assert 0 <= value <= 100
