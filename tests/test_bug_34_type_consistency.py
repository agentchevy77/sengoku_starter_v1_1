"""
Test suite for Bug #34: Inconsistent Data Types in Snapshot

Validates that all score-related fields in symbol snapshots use consistent
int types (0-100 range) without mixing float values.

This fixes the type ambiguity that creates problems for API consumers who
expect uniform score types across all fields.
"""

import pytest

from optipanel.chips.aggregate import compute_sustainment
from optipanel.engine.aggregate import build_symbol_snapshot

# Test data with comprehensive timeframe bundles
FULL_FEATURES = {
    "symbol": "TSLA",
    "last": 250.50,
    "dma20": 245.00,
    "support": 240.00,
    "resistance": 260.00,
    "rvol": 1.8,
    "rs_strength": 0.35,
    "vwap_diff": 0.015,
    "bundles": {
        "1d": {
            "last": 250.50,
            "dma20": 245.00,
            "support": 240.00,
            "resistance": 260.00,
            "rvol": 1.8,
            "rs_strength": 0.35,
            "vwap_diff": 0.015,
            "donchian_pos": 0.88,
            "obv_slope": 0.62,
            "chaikin_ad": 0.54,
            "clv": 0.48,
            "avwap_diff": 0.018,
            "vwap_confluence": 0.72,
        },
        "60m": {
            "last": 249.80,
            "dma20": 244.50,
            "support": 239.00,
            "resistance": 259.50,
            "rvol": 1.5,
            "rs_strength": 0.28,
            "vwap_diff": 0.012,
            "donchian_pos": 0.82,
            "obv_slope": 0.55,
            "chaikin_ad": 0.47,
            "clv": 0.41,
            "avwap_diff": 0.014,
            "vwap_confluence": 0.65,
        },
        "15m": {
            "last": 250.10,
            "dma20": 245.20,
            "support": 240.50,
            "resistance": 259.80,
            "rvol": 1.3,
            "rs_strength": 0.22,
            "vwap_diff": 0.009,
            "donchian_pos": 0.76,
            "obv_slope": 0.48,
            "chaikin_ad": 0.39,
            "clv": 0.35,
            "avwap_diff": 0.011,
            "vwap_confluence": 0.58,
        },
    },
}


def test_compute_sustainment_returns_only_ints():
    """Test that compute_sustainment returns only int values, no floats."""

    # Create sample prob chips data
    chips_by_tf = {
        "1d": {
            "trend_long": 75,
            "trend_short": 25,
            "breakout_up": 80,
            "rejection_down": 20,
            "bounce_up": 65,
            "breakdown_down": 30,
        },
        "60m": {
            "trend_long": 70,
            "trend_short": 30,
            "breakout_up": 75,
            "rejection_down": 25,
            "bounce_up": 60,
            "breakdown_down": 35,
        },
    }

    result = compute_sustainment(chips_by_tf)

    # Validate structure
    assert isinstance(result, dict), "Result must be a dict"
    assert "sustainability" in result, "Must contain sustainability"
    assert "fakeout_risk" in result, "Must contain fakeout_risk"

    # Validate types - CRITICAL: All values must be int
    assert isinstance(result["sustainability"], int), "sustainability must be int"
    assert isinstance(result["fakeout_risk"], int), "fakeout_risk must be int"

    # Validate no float values anywhere
    for key, value in result.items():
        assert not isinstance(value, float), f"Field '{key}' contains float value: {value}"
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                assert not isinstance(subvalue, float), f"Nested field '{key}.{subkey}' contains float: {subvalue}"

    # Validate ranges
    assert 0 <= result["sustainability"] <= 100, "sustainability must be in 0-100 range"
    assert 0 <= result["fakeout_risk"] <= 100, "fakeout_risk must be in 0-100 range"


def test_compute_sustainment_empty_input():
    """Test that empty input returns proper int defaults."""

    result = compute_sustainment(None)

    assert result == {"sustainability": 50, "fakeout_risk": 50}
    assert isinstance(result["sustainability"], int)
    assert isinstance(result["fakeout_risk"], int)


def test_snapshot_all_scores_are_ints():
    """Comprehensive test: All score-related fields in snapshot must be int."""

    snapshot = build_symbol_snapshot("TSLA", FULL_FEATURES)

    # Top-level score field
    assert isinstance(snapshot["score"], int), "Main score must be int"
    assert 0 <= snapshot["score"] <= 100, "Score must be in 0-100 range"

    # Setups: All values must be int
    setups = snapshot["setups"]
    assert isinstance(setups, dict), "setups must be dict"
    for setup_name, setup_value in setups.items():
        assert isinstance(
            setup_value, int
        ), f"Setup '{setup_name}' has value {setup_value} (type {type(setup_value).__name__}), expected int"
        assert 0 <= setup_value <= 100, f"Setup '{setup_name}' value {setup_value} out of 0-100 range"

    # Units: All nested values must be int
    units = snapshot["units"]
    assert isinstance(units, dict), "units must be dict"
    for unit_name, unit_dict in units.items():
        assert isinstance(unit_dict, dict), f"Unit '{unit_name}' must be dict"
        for sub_key, sub_value in unit_dict.items():
            assert isinstance(
                sub_value, int
            ), f"Unit '{unit_name}.{sub_key}' has value {sub_value} (type {type(sub_value).__name__}), expected int"
            assert 0 <= sub_value <= 100, f"Unit '{unit_name}.{sub_key}' value {sub_value} out of 0-100 range"

    # Sustainment: All values must be int (Bug #34 fix target)
    sustainment = snapshot["sustainment"]
    assert isinstance(sustainment, dict), "sustainment must be dict"
    for sus_key, sus_value in sustainment.items():
        assert isinstance(
            sus_value, int
        ), f"Sustainment '{sus_key}' has value {sus_value} (type {type(sus_value).__name__}), expected int"
        assert 0 <= sus_value <= 100, f"Sustainment '{sus_key}' value {sus_value} out of 0-100 range"

    # Prob chips: All values must be int
    prob_chips = snapshot["prob_chips"]
    assert isinstance(prob_chips, dict), "prob_chips must be dict"
    for tf_key, tf_dict in prob_chips.items():
        assert isinstance(tf_dict, dict), f"Prob chip timeframe '{tf_key}' must be dict"
        for chip_name, chip_value in tf_dict.items():
            assert isinstance(
                chip_value, int
            ), f"Prob chip '{tf_key}.{chip_name}' has value {chip_value} (type {type(chip_value).__name__}), expected int"
            assert 0 <= chip_value <= 100, f"Prob chip '{tf_key}.{chip_name}' value {chip_value} out of 0-100 range"

    # Prob summary: All values must be int
    prob_summary = snapshot["prob_summary"]
    assert isinstance(prob_summary, dict), "prob_summary must be dict"
    for tf_key, summary_dict in prob_summary.items():
        assert isinstance(summary_dict, dict), f"Prob summary timeframe '{tf_key}' must be dict"
        for metric_name, metric_value in summary_dict.items():
            assert isinstance(
                metric_value, int
            ), f"Prob summary '{tf_key}.{metric_name}' has value {metric_value} (type {type(metric_value).__name__}), expected int"
            assert (
                0 <= metric_value <= 100
            ), f"Prob summary '{tf_key}.{metric_name}' value {metric_value} out of 0-100 range"


def test_snapshot_no_debug_field_in_sustainment():
    """Verify that sustainment does not contain debug field with floats."""

    snapshot = build_symbol_snapshot("TSLA", FULL_FEATURES)
    sustainment = snapshot["sustainment"]

    # The bug was that sustainment contained a "debug" field with float values
    # After fix, sustainment should only contain int scores
    assert "debug" not in sustainment, "sustainment must not contain 'debug' field (should only have int scores)"

    # Explicitly verify no nested dicts with float values
    for key, value in sustainment.items():
        if isinstance(value, dict):
            pytest.fail(f"sustainment['{key}'] contains nested dict (expected only int values): {value}")


def test_snapshot_type_consistency_edge_cases():
    """Test type consistency with edge case inputs."""

    # Minimal features
    minimal = {
        "last": 100.0,
        "dma20": 100.0,
        "support": 95.0,
        "resistance": 105.0,
        "rvol": 1.0,
        "rs_strength": 0.0,
        "vwap_diff": 0.0,
    }

    snapshot = build_symbol_snapshot("TEST", minimal)

    # Even with minimal data, all scores must be int
    assert isinstance(snapshot["score"], int)
    assert all(isinstance(v, int) for v in snapshot["setups"].values())
    assert all(isinstance(v, int) for v in snapshot["sustainment"].values())

    # Verify no float contamination
    def check_no_floats_in_scores(obj, path=""):
        """Recursively check that score dicts don't contain floats."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("battlefield_bundle", "features"):
                    # These are allowed to have floats (raw market data)
                    continue
                new_path = f"{path}.{key}" if path else key
                if isinstance(value, float) and key not in (
                    "last",
                    "dma20",
                    "support",
                    "resistance",
                    "rvol",
                    "rs_strength",
                    "vwap_diff",
                ):
                    pytest.fail(f"Float found in score field at {new_path}: {value}")
                if isinstance(value, dict):
                    check_no_floats_in_scores(value, new_path)

    # Check all score-related fields
    score_fields = {
        "score": snapshot["score"],
        "setups": snapshot["setups"],
        "units": snapshot["units"],
        "sustainment": snapshot["sustainment"],
        "prob_chips": snapshot["prob_chips"],
        "prob_summary": snapshot["prob_summary"],
    }

    for field_name, field_value in score_fields.items():
        check_no_floats_in_scores(field_value, field_name)


def test_api_serialization_compatibility():
    """Verify snapshot can be JSON-serialized without type issues."""

    import json

    snapshot = build_symbol_snapshot("AAPL", FULL_FEATURES)

    # Should serialize cleanly to JSON
    try:
        json_str = json.dumps(snapshot)
        assert json_str, "Snapshot must serialize to non-empty JSON"
    except (TypeError, ValueError) as e:
        pytest.fail(f"Snapshot failed to serialize to JSON: {e}")

    # Round-trip test
    deserialized = json.loads(json_str)

    # After deserialization, all score values should still be int (not float)
    # Note: JSON may convert int to float in some cases, but our ints should stay ints
    assert isinstance(deserialized["score"], int)
    assert isinstance(deserialized["sustainment"]["sustainability"], int)
    assert isinstance(deserialized["sustainment"]["fakeout_risk"], int)


if __name__ == "__main__":
    # Allow running test file directly for debugging
    pytest.main([__file__, "-v"])
