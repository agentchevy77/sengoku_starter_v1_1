"""
Characterization test for SetupConfig refactoring.

This test captures the exact behavior of the original compute_setups function
to ensure the refactoring preserves mathematical equivalence.

The "golden master" outputs were generated from the original implementation
and must not change during refactoring.
"""

from optipanel.setups.engine import compute_setups


def test_bullish_breakout_scenario():
    """
    Scenario: Price just broke above resistance with strong momentum.
    - last > resistance (breakout confirmed)
    - High rvol (1.5) and positive rs (0.15)
    - Above dma20 (bullish)
    """
    features = {
        "last": 101.5,
        "dma20": 100.0,
        "resistance": 101.0,
        "support": 99.0,
        "rvol": 1.5,
        "rs_strength": 0.15,
        "vwap_diff": 0.2,
    }

    expected = {
        "breakout_up": 100,
        "breakdown_down": 40,
        "bounce_up": 55,
        "rejection_down": 25,
        "trend_long": 90,
        "trend_short": 35,
        "exhaustion": 40,
    }

    actual = compute_setups(features)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_bearish_breakdown_scenario():
    """
    Scenario: Price broke below support with strong bearish momentum.
    - last < support (breakdown confirmed)
    - High rvol (1.8) and negative rs (-0.15)
    - Below dma20 (bearish)
    """
    features = {
        "last": 98.5,
        "dma20": 100.0,
        "resistance": 101.0,
        "support": 99.0,
        "rvol": 1.8,
        "rs_strength": -0.15,
        "vwap_diff": -0.3,
    }

    expected = {
        "breakout_up": 40,
        "breakdown_down": 100,
        "bounce_up": 20,
        "rejection_down": 55,
        "trend_long": 35,
        "trend_short": 90,
        "exhaustion": 40,
    }

    actual = compute_setups(features)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_neutral_ranging_scenario():
    """
    Scenario: Price trading between support and resistance, no clear trend.
    - last == dma20 (neutral)
    - Moderate distance from both support and resistance
    - Normal volume (rvol = 1.0)
    """
    features = {
        "last": 100.0,
        "dma20": 100.0,
        "resistance": 101.0,
        "support": 99.0,
        "rvol": 1.0,
        "rs_strength": 0.0,
        "vwap_diff": 0.0,
    }

    expected = {
        "breakout_up": 65,
        "breakdown_down": 60,
        "bounce_up": 70,
        "rejection_down": 60,
        "trend_long": 70,
        "trend_short": 40,
        "exhaustion": 30,
    }

    actual = compute_setups(features)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_high_exhaustion_scenario():
    """
    Scenario: Price extended far from dma20 with extreme volume.
    - last = 108, dma20 = 100 (8% extension)
    - Very high rvol (2.0)
    - Should trigger high exhaustion score
    """
    features = {
        "last": 108.0,
        "dma20": 100.0,
        "resistance": 105.0,
        "support": 95.0,
        "rvol": 2.0,
        "rs_strength": 0.2,
        "vwap_diff": 0.5,
    }

    expected = {
        "breakout_up": 100,
        "breakdown_down": 40,
        "bounce_up": 55,
        "rejection_down": 25,
        "trend_long": 90,
        "trend_short": 35,
        "exhaustion": 80,  # High exhaustion due to 8% extension + high rvol
    }

    actual = compute_setups(features)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_missing_optional_fields():
    """
    Scenario: Only required fields provided, optional fields use defaults.
    - No rvol (defaults to 1.0)
    - No rs_strength (defaults to 0.0)
    - No vwap_diff (defaults to 0.0)
    """
    features = {
        "last": 100.0,
        "dma20": 98.0,
        "resistance": 102.0,
        "support": 97.0,
    }

    expected = {
        "breakout_up": 35,
        "breakdown_down": 30,
        "bounce_up": 55,
        "rejection_down": 45,
        "trend_long": 70,
        "trend_short": 40,
        "exhaustion": 30,
    }

    actual = compute_setups(features)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_edge_case_zero_values():
    """
    Scenario: Test defensive handling of edge case inputs.
    - Very small or zero values should not crash
    """
    features = {
        "last": 0.01,
        "dma20": 0.01,
        "resistance": 0.02,
        "support": 0.005,
        "rvol": 0.0,
        "rs_strength": 0.0,
        "vwap_diff": 0.0,
    }

    # Just verify it doesn't crash and returns valid scores
    actual = compute_setups(features)
    assert isinstance(actual, dict)
    assert all(0 <= v <= 100 for v in actual.values())
