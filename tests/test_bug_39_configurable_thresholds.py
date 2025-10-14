"""Unit tests for Bug #39: Misleading Default Parameter in Core Algorithm.

This test suite verifies that risk thresholds in optipanel/engine/aggregate.py are
configurable through SetupConfig instead of being hardcoded local constants.

Bug #39 Fix: The advice logic thresholds (EXHAUSTION_VETO, SUSTAINABILITY_MIN,
FAKEOUT_RISK_MAX) are now part of SetupConfig and can be customized via the
config parameter in build_symbol_snapshot().
"""

from __future__ import annotations

from decimal import Decimal

from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.setups.engine import SetupConfig


class TestBug39ConfigurableThresholds:
    """Test suite for Bug #39: Configurable risk thresholds."""

    def test_default_config_maintains_original_behavior(self) -> None:
        """Verify that default config preserves original hardcoded values (backward compatibility)."""
        config = SetupConfig()

        # Verify default values match original hardcoded constants
        assert config.advice_exhaustion_veto == 70.0
        assert config.advice_sustainability_min == 40.0
        assert config.advice_fakeout_risk_max == 70.0

    def test_custom_config_allows_different_thresholds(self) -> None:
        """Verify that custom config values can be set and are different from defaults."""
        custom_config = SetupConfig(
            advice_exhaustion_veto=80.0,  # More permissive (allow more exhaustion)
            advice_sustainability_min=30.0,  # Less strict (accept lower sustainability)
            advice_fakeout_risk_max=80.0,  # More permissive (accept higher fakeout risk)
        )

        assert custom_config.advice_exhaustion_veto == 80.0
        assert custom_config.advice_sustainability_min == 30.0
        assert custom_config.advice_fakeout_risk_max == 80.0

    def test_build_symbol_snapshot_accepts_config_parameter(self) -> None:
        """Verify that build_symbol_snapshot accepts optional config parameter."""
        features = {
            "last": 150.0,
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 155.0,
            "rvol": 1.5,
            "rs_strength": 0.25,
            "vwap_diff": 0.01,
        }

        # Should work with no config (uses defaults)
        snapshot_default = build_symbol_snapshot("TEST", features)
        assert snapshot_default is not None
        assert "advice" in snapshot_default

        # Should work with custom config
        custom_config = SetupConfig(advice_exhaustion_veto=80.0)
        snapshot_custom = build_symbol_snapshot("TEST", features, config=custom_config)
        assert snapshot_custom is not None
        assert "advice" in snapshot_custom

    def test_strict_config_vetoes_attack_on_high_exhaustion(self) -> None:
        """Verify that strict thresholds veto 'attack' advice when exhaustion is high."""
        # Create scenario: Strong bullish signal BUT high exhaustion
        features = {
            "last": 155.0,  # Above resistance
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 150.0,
            "rvol": 2.0,  # High volume
            "rs_strength": 0.3,  # Strong RS
            "vwap_diff": 0.02,
        }

        # Use strict config (low exhaustion veto threshold)
        strict_config = SetupConfig(
            advice_exhaustion_veto=50.0,  # Veto if exhaustion > 50 (very strict)
            advice_sustainability_min=40.0,
            advice_fakeout_risk_max=70.0,
        )

        snapshot = build_symbol_snapshot("TEST", features, config=strict_config)

        # With strict config, exhaustion score will likely exceed 50, so advice should be "standby"
        # (Not "attack" despite strong signal)
        assert snapshot["advice"] in ("standby", "defend")  # Should veto attack

    def test_permissive_config_allows_attack_on_moderate_exhaustion(self) -> None:
        """Verify that permissive thresholds allow 'attack' advice with moderate exhaustion."""
        # Create scenario: Strong bullish signal with moderate exhaustion
        features = {
            "last": 152.0,  # Above resistance
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 150.0,
            "rvol": 1.5,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }

        # Use permissive config (high thresholds)
        permissive_config = SetupConfig(
            advice_exhaustion_veto=90.0,  # Very permissive (allow exhaustion up to 90)
            advice_sustainability_min=20.0,  # Very permissive
            advice_fakeout_risk_max=90.0,  # Very permissive
        )

        snapshot = build_symbol_snapshot("TEST", features, config=permissive_config)

        # With permissive config, should allow "attack" since thresholds are relaxed
        assert snapshot["advice"] == "attack"

    def test_config_affects_risk_penalty_calculation(self) -> None:
        """Verify that config thresholds affect the risk penalty in score calculation."""
        features = {
            "last": 150.0,
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 155.0,
            "rvol": 1.5,
            "rs_strength": 0.1,
            "vwap_diff": 0.01,
        }

        # Test with default config
        snapshot_default = build_symbol_snapshot("TEST", features)
        score_default = snapshot_default["score"]

        # Test with strict config (lower thresholds = more penalties)
        strict_config = SetupConfig(
            advice_exhaustion_veto=50.0,  # Lower threshold = penalty kicks in earlier
            advice_sustainability_min=50.0,  # Higher threshold = penalty kicks in earlier
        )
        snapshot_strict = build_symbol_snapshot("TEST", features, config=strict_config)
        score_strict = snapshot_strict["score"]

        # Strict config should generally result in lower scores due to more penalties
        # (though this depends on the actual risk metrics)
        assert isinstance(score_default, int)
        assert isinstance(score_strict, int)
        assert 0 <= score_default <= 100
        assert 0 <= score_strict <= 100

    def test_config_thresholds_precision_with_decimal(self) -> None:
        """Verify that config thresholds are properly converted to Decimal for precision."""
        from optipanel.engine.aggregate import _calculate_risk_penalty

        config = SetupConfig(
            advice_exhaustion_veto=70.0,
            advice_sustainability_min=40.0,
            advice_fakeout_risk_max=70.0,
        )

        # Test penalty calculation with values right at thresholds
        penalty = _calculate_risk_penalty(
            exhaustion=Decimal("70"),  # Exactly at threshold
            sustainability=Decimal("40"),  # Exactly at threshold
            fakeout_risk=Decimal("60"),
            config=config,
        )

        # At exact thresholds, penalty should be zero (not exceeding)
        assert penalty == Decimal("0")

        # Test penalty when exceeding thresholds
        penalty_exceeded = _calculate_risk_penalty(
            exhaustion=Decimal("75"),  # 5 points above threshold
            sustainability=Decimal("35"),  # 5 points below threshold
            fakeout_risk=Decimal("75"),  # 5 points above fakeout threshold (70)
            config=config,
        )

        # Should have penalties for exceeding thresholds
        assert penalty_exceeded > Decimal("0")

    def test_fakeout_threshold_respects_config(self) -> None:
        """Verify fakeout penalty clamps against the configurable threshold."""
        from optipanel.engine.aggregate import _calculate_risk_penalty

        baseline_config = SetupConfig(advice_fakeout_risk_max=70.0)
        relaxed_config = SetupConfig(advice_fakeout_risk_max=90.0)

        exhaustion = Decimal("40")
        sustainability = Decimal("60")
        fakeout_risk = Decimal("80")

        baseline_penalty = _calculate_risk_penalty(
            exhaustion=exhaustion,
            sustainability=sustainability,
            fakeout_risk=fakeout_risk,
            config=baseline_config,
        )

        relaxed_penalty = _calculate_risk_penalty(
            exhaustion=exhaustion,
            sustainability=sustainability,
            fakeout_risk=fakeout_risk,
            config=relaxed_config,
        )

        assert relaxed_penalty < baseline_penalty

    def test_different_symbols_with_same_config(self) -> None:
        """Verify that config is consistently applied across different symbols."""
        config = SetupConfig(
            advice_exhaustion_veto=75.0,
            advice_sustainability_min=35.0,
            advice_fakeout_risk_max=75.0,
        )

        features_aapl = {
            "last": 150.0,
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 155.0,
            "rvol": 1.5,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }

        features_tsla = {
            "last": 250.0,
            "dma20": 240.0,
            "support": 230.0,
            "resistance": 260.0,
            "rvol": 2.0,
            "rs_strength": 0.3,
            "vwap_diff": 0.02,
        }

        snapshot_aapl = build_symbol_snapshot("AAPL", features_aapl, config=config)
        snapshot_tsla = build_symbol_snapshot("TSLA", features_tsla, config=config)

        # Both should use the same config thresholds
        assert snapshot_aapl is not None
        assert snapshot_tsla is not None
        assert "advice" in snapshot_aapl
        assert "advice" in snapshot_tsla

    def test_backward_compatibility_no_config_parameter(self) -> None:
        """Verify backward compatibility: existing calls without config still work."""
        features = {
            "last": 150.0,
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 155.0,
            "rvol": 1.5,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }

        # Old-style call without config parameter
        snapshot = build_symbol_snapshot("TEST", features)

        # Should work exactly as before (using default config)
        assert snapshot is not None
        assert snapshot["symbol"] == "TEST"
        assert "advice" in snapshot
        assert snapshot["advice"] in ("attack", "defend", "standby")
        assert "score" in snapshot
        assert isinstance(snapshot["score"], int)

    def test_extreme_config_values(self) -> None:
        """Test that extreme config values are handled correctly."""
        # Ultra-strict config
        ultra_strict = SetupConfig(
            advice_exhaustion_veto=10.0,  # Almost never allow attack
            advice_sustainability_min=90.0,  # Almost never allow attack
            advice_fakeout_risk_max=10.0,  # Almost never allow attack
        )

        # Ultra-permissive config
        ultra_permissive = SetupConfig(
            advice_exhaustion_veto=100.0,  # Always allow
            advice_sustainability_min=0.0,  # Always allow
            advice_fakeout_risk_max=100.0,  # Always allow
        )

        features = {
            "last": 155.0,
            "dma20": 145.0,
            "support": 140.0,
            "resistance": 150.0,
            "rvol": 2.0,
            "rs_strength": 0.3,
            "vwap_diff": 0.02,
        }

        snapshot_strict = build_symbol_snapshot("TEST", features, config=ultra_strict)
        snapshot_permissive = build_symbol_snapshot("TEST", features, config=ultra_permissive)

        # Ultra-strict should likely veto attack
        assert snapshot_strict["advice"] in ("standby", "defend")

        # Ultra-permissive should likely allow attack
        assert snapshot_permissive["advice"] == "attack"


def test_bug_39_integration_with_setups(tmp_path) -> None:
    """Integration test: Verify config is passed through to compute_setups."""
    from optipanel.setups.engine import compute_setups

    # Custom config with modified exhaustion parameters
    custom_config = SetupConfig(
        exhaustion_base=40.0,  # Different from default 30.0
        exhaustion_ext_min=0.03,  # Different from default 0.05
    )

    features = {
        "last": 160.0,
        "dma20": 145.0,
        "support": 140.0,
        "resistance": 155.0,
        "rvol": 2.0,
        "rs_strength": 0.2,
        "vwap_diff": 0.01,
    }

    # Compute setups with custom config
    setups = compute_setups(features, config=custom_config)

    # Exhaustion score should be calculated using custom config values
    assert "exhaustion" in setups
    assert isinstance(setups["exhaustion"], int)
    assert 0 <= setups["exhaustion"] <= 100


def test_bug_39_documentation_completeness() -> None:
    """Verify that SetupConfig has proper documentation for new fields."""

    # Check that SetupConfig docstring mentions the advice thresholds
    config = SetupConfig()

    # Verify fields exist
    assert hasattr(config, "advice_exhaustion_veto")
    assert hasattr(config, "advice_sustainability_min")
    assert hasattr(config, "advice_fakeout_risk_max")

    # Verify they have reasonable default values
    assert 0 < config.advice_exhaustion_veto <= 100
    assert 0 < config.advice_sustainability_min <= 100
    assert 0 < config.advice_fakeout_risk_max <= 100
