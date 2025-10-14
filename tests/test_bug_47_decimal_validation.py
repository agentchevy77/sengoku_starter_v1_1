#!/usr/bin/env python3
"""Simplified unit tests for Bug #47: Decimal validation in position calculations.

This test module verifies that invalid Decimal values (0, NaN, inf) are
properly validated before use in critical financial calculations.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optipanel.positions.model import (
    D_ZERO,
    Position,
    PositionState,
    _coerce_price,
)


class TestDecimalValidation:
    """Test suite for Decimal validation (Bug #47)."""

    def test_coerce_price_handles_nan(self):
        """Test that _coerce_price properly handles NaN values."""
        assert _coerce_price(float("nan")) is None

    def test_coerce_price_handles_inf(self):
        """Test that _coerce_price properly handles infinity values."""
        assert _coerce_price(float("inf")) is None
        assert _coerce_price(float("-inf")) is None

    def test_coerce_price_handles_zero(self):
        """Test that _coerce_price rejects zero and negative values."""
        assert _coerce_price(0) is None
        assert _coerce_price(0.0) is None
        assert _coerce_price(Decimal("0")) is None
        assert _coerce_price(-1) is None
        assert _coerce_price(Decimal("-1")) is None

    def test_coerce_price_accepts_valid_values(self):
        """Test that _coerce_price accepts valid positive values."""
        result = _coerce_price(100.50)
        assert result == Decimal("100.5")

        result = _coerce_price("150.25")
        assert result == Decimal("150.25")

        result = _coerce_price(Decimal("200.75"))
        assert result == Decimal("200.75")


class TestShouldExitValidation:
    """Test _should_exit method with invalid Decimal values."""

    @pytest.fixture
    def model(self):
        """Create a PositionState with test data."""
        model = PositionState(cash=Decimal("10000.00"))
        # Add a test position
        model.positions["AAPL"] = Position("AAPL", 100, Decimal("150.00"))
        return model

    @pytest.fixture
    def thresholds(self):
        """Create test thresholds."""
        return {
            "exit_breakdown": 80,
            "exit_trend": 70,
            "stop_loss": -0.05,  # -5%
            "take_profit": 0.10,  # +10%
        }

    def test_should_exit_with_none_last(self, model, thresholds):
        """Test that _should_exit handles None last price without crashing."""
        result = model._should_exit("AAPL", None, {}, thresholds)
        assert result is False

    def test_should_exit_with_zero_last(self, model, thresholds):
        """Test that _should_exit handles zero last price without crashing."""
        result = model._should_exit("AAPL", D_ZERO, {}, thresholds)
        assert result is False

    def test_should_exit_with_negative_last(self, model, thresholds):
        """Test that _should_exit handles negative last price without crashing."""
        result = model._should_exit("AAPL", Decimal("-100"), {}, thresholds)
        assert result is False

    def test_should_exit_with_inf_last(self, model, thresholds):
        """Test that _should_exit handles infinite last price without crashing."""
        inf_decimal = Decimal("Infinity")
        result = model._should_exit("AAPL", inf_decimal, {}, thresholds)
        assert result is False

    def test_should_exit_with_nan_last(self, model, thresholds):
        """Test that _should_exit handles NaN last price without crashing."""
        nan_decimal = Decimal("NaN")
        result = model._should_exit("AAPL", nan_decimal, {}, thresholds)
        assert result is False

    def test_should_exit_with_invalid_avg_px(self, model, thresholds):
        """Test that _should_exit handles invalid avg_px in position."""
        # Create position with zero avg_px
        model.positions["BAD"] = Position("BAD", 100, D_ZERO)

        result = model._should_exit("BAD", Decimal("100"), {}, thresholds)

        # Should not crash, returns False safely
        assert result is False

    def test_should_exit_with_tiny_avg_px(self, model, thresholds):
        """Test that _should_exit handles very small avg_px."""
        # Create position with tiny avg_px
        model.positions["TINY"] = Position("TINY", 100, Decimal("1e-10"))

        result = model._should_exit("TINY", Decimal("100"), {}, thresholds)

        # Should use zero change and not crash
        assert result is False

    def test_should_exit_with_valid_values(self, model, thresholds):
        """Test that _should_exit works correctly with valid values."""
        # Test normal operation - no exit
        result = model._should_exit("AAPL", Decimal("152"), {}, thresholds)
        assert result is False  # Small gain, not at take profit

        # Test take profit exit
        result = model._should_exit("AAPL", Decimal("170"), {}, thresholds)
        assert result is True  # 13.3% gain > 10% take profit

        # Test stop loss exit
        result = model._should_exit("AAPL", Decimal("140"), {}, thresholds)
        assert result is True  # -6.7% loss < -5% stop loss


class TestEdgeCases:
    """Test edge cases with Decimal operations."""

    @pytest.fixture
    def model(self):
        """Create a PositionState."""
        model = PositionState(cash=Decimal("10000.00"))
        model.positions["EDGE"] = Position("EDGE", 100, Decimal("100"))
        return model

    def test_change_calculation_with_edge_values(self, model):
        """Test change calculation with edge values."""
        thresholds = {
            "exit_breakdown": 80,
            "exit_trend": 70,
            "stop_loss": -0.05,
            "take_profit": 0.10,
        }

        # Test with exact same price (0% change)
        result = model._should_exit("EDGE", Decimal("100"), {}, thresholds)
        assert result is False

        # Test with very small change
        result = model._should_exit("EDGE", Decimal("100.01"), {}, thresholds)
        assert result is False

        # Test with large price
        result = model._should_exit("EDGE", Decimal("1000000"), {}, thresholds)
        assert result is True  # Massive gain triggers take profit

    def test_non_finite_change_result(self, model):
        """Test handling of positions with extreme values."""
        # Create a position that could theoretically produce edge cases
        model.positions["WEIRD"] = Position("WEIRD", 100, Decimal("1e-300"))

        thresholds = {
            "exit_breakdown": 80,
            "exit_trend": 70,
            "stop_loss": -0.05,
            "take_profit": 0.10,
        }

        # Very large price relative to tiny avg_px
        # Should handle gracefully without crash
        result = model._should_exit("WEIRD", Decimal("1e300"), {}, thresholds)

        # The validation should prevent invalid calculations
        assert isinstance(result, bool)


class TestIntegration:
    """Integration tests for full workflow."""

    def test_coerce_price_integration(self):
        """Test that _coerce_price is used correctly in the flow."""
        # These would normally be rejected by _coerce_price upstream
        assert _coerce_price(0) is None
        assert _coerce_price(float("nan")) is None
        assert _coerce_price(float("inf")) is None

        # Valid prices pass through
        assert _coerce_price(100.0) == Decimal("100")
        assert _coerce_price(Decimal("50.25")) == Decimal("50.25")

    def test_no_crash_on_invalid_inputs(self):
        """Test that system doesn't crash with various invalid inputs."""
        model = PositionState(cash=Decimal("10000"))
        model.positions["TEST"] = Position("TEST", 100, Decimal("100"))

        thresholds = {
            "exit_breakdown": 80,
            "exit_trend": 70,
            "stop_loss": -0.05,
            "take_profit": 0.10,
        }

        # Try various invalid inputs - none should crash
        invalid_inputs = [
            None,
            D_ZERO,
            Decimal("-1"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            Decimal("NaN"),
        ]

        for invalid_value in invalid_inputs:
            result = model._should_exit("TEST", invalid_value, {}, thresholds)
            # Should always return a boolean
            assert isinstance(result, bool)
            # Should return False for invalid inputs
            assert result is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
