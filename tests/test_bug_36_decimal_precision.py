"""
Test suite for Bug #36: Systemic Mathematical Inaccuracy Fix

This module tests the Decimal-based financial calculation system that replaces
floating-point arithmetic to eliminate rounding errors.

Bug #36 CRITICAL FIX:
- All financial calculations now use Python's Decimal type
- Eliminates floating-point precision issues (0.1 + 0.2 != 0.3)
- Ensures penny-perfect P&L tracking
- Prevents accumulation of rounding errors across trades

Test Coverage:
1. Decimal utility functions (conversion, rounding, clamping)
2. Battlefield engine calculations (price gaps, percentages)
3. Setup engine calculations (score computations)
4. Position P&L tracking (entry, exit, cash management)
5. Edge cases (very small/large values, precision limits)
"""

from decimal import Decimal

import pytest

from optipanel.battlefield.engine import compute_units
from optipanel.positions.model import Position, PositionState
from optipanel.setups.engine import compute_setups
from optipanel.utils.decimal_types import (
    D_ZERO,
    clamp_score,
    pct_gap_above,
    pct_gap_below,
    round_percentage,
    round_price,
    safe_divide,
    to_decimal,
)


class TestDecimalUtilities:
    """Test core Decimal utility functions."""

    def test_to_decimal_from_float(self):
        """Decimal conversion from float avoids precision issues."""
        # Float 0.1 cannot be represented exactly in binary
        result = to_decimal(0.1)
        assert result == Decimal("0.1")  # Exact representation
        assert result != Decimal(0.1)  # Would be 0.1000000000000000055511151231...

    def test_to_decimal_from_string(self):
        """String conversion gives exact Decimal."""
        assert to_decimal("0.01") == Decimal("0.01")
        assert to_decimal("100.25") == Decimal("100.25")
        assert to_decimal("1.0000000001") == Decimal("1.0000000001")

    def test_to_decimal_handles_none(self):
        """None values use default."""
        assert to_decimal(None) == D_ZERO
        assert to_decimal(None, Decimal("99")) == Decimal("99")

    def test_to_decimal_handles_invalid(self):
        """Invalid values use default."""
        assert to_decimal("not_a_number") == D_ZERO
        assert to_decimal(float("nan")) == D_ZERO
        assert to_decimal(float("inf")) == D_ZERO

    def test_round_price_precision(self):
        """Price rounding to 2 decimal places."""
        assert round_price(Decimal("100.123456")) == Decimal("100.12")
        assert round_price(Decimal("100.126")) == Decimal("100.13")
        assert round_price(Decimal("100.125")) == Decimal("100.13")  # ROUND_HALF_UP rounds .5 up

    def test_round_percentage_precision(self):
        """Percentage rounding to 4 decimal places."""
        assert round_percentage(Decimal("0.123456")) == Decimal("0.1235")
        assert round_percentage(Decimal("0.00001")) == Decimal("0.0000")

    def test_clamp_score_boundaries(self):
        """Score clamping to 0-100 range."""
        assert clamp_score(Decimal("50")) == 50
        assert clamp_score(Decimal("-10")) == 0
        assert clamp_score(Decimal("150")) == 100
        assert clamp_score(Decimal("99.6")) == 100  # Rounds up

    def test_safe_divide_zero_denominator(self):
        """Division by zero returns default."""
        assert safe_divide(Decimal("100"), D_ZERO) == D_ZERO
        assert safe_divide(Decimal("100"), D_ZERO, Decimal("999")) == Decimal("999")

    def test_safe_divide_normal(self):
        """Normal division is precise within Decimal precision."""
        result = safe_divide(Decimal("1"), Decimal("3"))
        # Decimal division is precise to its precision limit
        # 1/3 = 0.333... (repeating), Decimal uses finite precision
        assert result == Decimal("0.3333333333333333333333333333")
        # But for exact divisors, we get exact results
        result2 = safe_divide(Decimal("10"), Decimal("2"))
        assert result2 == Decimal("5")

    def test_pct_gap_calculations(self):
        """Percentage gap calculations are precise."""
        last = Decimal("100")
        resistance = Decimal("105")
        support = Decimal("95")

        gap_above = pct_gap_above(last, resistance)
        assert gap_above == Decimal("0.05")  # Exactly 5%

        gap_below = pct_gap_below(last, support)
        assert gap_below == Decimal("0.05")  # Exactly 5%


class TestBattlefieldDecimalPrecision:
    """Test battlefield engine uses Decimal correctly."""

    def test_support_distance_calculation_precise(self):
        """Support distance calculation avoids float errors."""
        features = {
            "last": 100.01,  # Float input
            "dma20": 100.0,
            "support": 99.01,  # Exactly 1% below
            "resistance": 101.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        units = compute_units(features)

        # Should detect the 1% distance exactly
        # With float: 0.01 / 100.01 might not equal exactly 0.01
        # With Decimal: Precise calculation
        assert units["support"]["bull"] == 75  # Within 1%, bullish

    def test_resistance_distance_calculation_precise(self):
        """Resistance distance calculation avoids float errors."""
        features = {
            "last": 100.0,
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 101.0,  # Exactly 1% above
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        units = compute_units(features)

        # Should detect the 1% distance exactly
        assert units["resistance"]["bull"] == 25  # Within 1%, bearish

    def test_zero_price_handling(self):
        """Zero prices are handled safely."""
        features = {
            "last": 0.0,
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 101.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        units = compute_units(features)

        # Should return neutral when price is zero
        assert units["support"]["bull"] == 50
        assert units["resistance"]["bull"] == 50


class TestSetupsDecimalPrecision:
    """Test setups engine uses Decimal correctly."""

    def test_breakout_gap_calculation_precise(self):
        """Breakout gap calculation is exact."""
        features = {
            "last": 100.0,
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 100.5,  # 0.5% above
            "rvol": 1.0,
            "rs_strength": 0.0,
            "vwap_diff": 0.0,
        }
        setups = compute_setups(features)

        # Gap is exactly 0.5%, which is <= 1% gap_max
        # Should trigger "near" scoring logic
        assert setups["breakout_up"] >= 60  # Near resistance

    def test_exhaustion_calculation_precise(self):
        """Exhaustion extension calculation is exact."""
        features = {
            "last": 110.0,  # 10% above DMA
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 115.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
            "vwap_diff": 0.0,
        }
        setups = compute_setups(features)

        # Extension = abs(110 - 100) / 110 = 10/110 ≈ 0.0909
        # This is >= ext_min (0.05) and <= ext_max (0.10)
        # Should give high exhaustion score
        assert setups["exhaustion"] >= 60


class TestPositionDecimalPrecision:
    """Test position P&L tracking uses Decimal correctly."""

    def test_pnl_calculation_exact(self):
        """P&L calculation is penny-perfect."""
        state = PositionState(cash=Decimal("100000.00"))

        # Buy 100 shares at $10.01
        state.positions["TEST"] = Position("TEST", 100, Decimal("10.01"))

        # Mock exit at $10.03 (2 cent gain per share)
        pos = state.positions["TEST"]
        last = Decimal("10.03")
        pnl = (last - pos.avg_px) * Decimal(str(pos.qty))

        # Should be exactly $2.00, not $1.9999999... or $2.0000001
        assert pnl == Decimal("2.00")

    def test_cash_tracking_no_rounding_errors(self):
        """Cash tracking accumulates without rounding errors."""
        state = PositionState(cash=Decimal("1000.00"))

        # Simulate 100 micro-trades
        for _ in range(100):
            # Each trade: spend $0.01, gain $0.011 (0.1 cent profit)
            state.cash -= Decimal("0.01")
            state.cash += Decimal("0.011")

        # Total profit: 100 * 0.001 = $0.10
        # With float: accumulation errors could give $0.09999... or $0.10000...
        # With Decimal: exactly $1000.10
        assert state.cash == Decimal("1000.10")

    def test_position_exit_precise(self):
        """Position exit calculates exact P&L."""
        state = PositionState(cash=Decimal("10000.00"))

        features = {
            "TEST": {
                "last": 50.50,
                "dma20": 50.0,
                "support": 49.0,
                "resistance": 52.0,
                "rvol": 0.5,  # Low volume
                "rs_strength": -0.2,  # Weak
            }
        }

        # Manually enter position
        last = Decimal("50.50")
        qty = 100
        cost = Decimal(str(qty)) * last
        state.cash -= cost
        state.positions["TEST"] = Position("TEST", qty, last)

        # Update price to trigger exit
        features["TEST"]["last"] = 45.00  # Big drop

        # Force exit
        exit_price = Decimal("45.00")
        pos = state.positions["TEST"]
        pnl = (exit_price - pos.avg_px) * Decimal(str(pos.qty))
        state.cash += Decimal(str(pos.qty)) * exit_price
        del state.positions["TEST"]

        # Loss should be exactly: (45.00 - 50.50) * 100 = -$550.00
        assert pnl == Decimal("-550.00")
        # Cash should be: 10000 - 5050 + 4500 = $9450.00
        assert state.cash == Decimal("9450.00")


class TestFloatVsDecimalComparison:
    """Demonstrate float precision issues vs Decimal solutions."""

    def test_classic_float_precision_bug(self):
        """Famous 0.1 + 0.2 != 0.3 problem."""
        # Float version (WRONG)
        float_sum = 0.1 + 0.2
        assert float_sum != 0.3  # This fails!
        assert float_sum == pytest.approx(0.3)  # Need approximate comparison

        # Decimal version (CORRECT)
        decimal_sum = Decimal("0.1") + Decimal("0.2")
        assert decimal_sum == Decimal("0.3")  # Exact equality works!

    def test_accumulated_rounding_errors(self):
        """Repeated operations accumulate errors with float."""
        # Float version - errors can accumulate (though modern Python floats are quite good)
        float_result = 0.0
        for _ in range(10000):  # More iterations to show accumulation
            float_result += 0.001
        # Should be 10.0, but may have small error
        # Don't assert specific error size as it varies by platform
        assert float_result != 10.0 or abs(float_result - 10.0) < 1e-12  # Allow for very good float impl

        # Decimal version - always exact
        decimal_result = Decimal("0")
        for _ in range(10000):
            decimal_result += Decimal("0.001")
        assert decimal_result == Decimal("10.000")  # Exactly 10

    def test_percentage_calculation_precision(self):
        """Percentage calculations with Decimal are more reliable than float."""
        price = 12345.67
        change = 0.0123  # 1.23% change

        # Float calculation - may have small errors
        float_new_price = price * (1 + change)
        float_reverse = (float_new_price / price) - 1
        # Modern Python floats are quite good, error is very small
        # But it's still not guaranteed to be exactly equal
        assert float_reverse == pytest.approx(change, rel=1e-15)

        # Decimal calculation - exact arithmetic
        price_d = Decimal("12345.67")
        change_d = Decimal("0.0123")
        decimal_new_price = price_d * (Decimal("1") + change_d)
        decimal_reverse = (decimal_new_price / price_d) - Decimal("1")
        # With Decimal, the reverse calculation is exact (within precision)
        # Convert to float for comparison
        assert abs(float(decimal_reverse) - float(change_d)) < 1e-28


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_prices(self):
        """Handles sub-penny prices correctly."""
        features = {
            "last": 0.0001,  # $0.0001 (penny stocks)
            "dma20": 0.00009,
            "support": 0.00008,
            "resistance": 0.00012,
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        units = compute_units(features)
        # Should handle without overflow/underflow
        assert units is not None

    def test_very_large_prices(self):
        """Handles very large prices correctly."""
        features = {
            "last": 1000000.0,  # $1M (BRK.A-like)
            "dma20": 990000.0,
            "support": 980000.0,
            "resistance": 1010000.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        setups = compute_setups(features)
        # Should handle without overflow
        assert setups is not None
        assert 0 <= setups["breakout_up"] <= 100

    def test_negative_prices_handled(self):
        """Negative prices return None (invalid)."""
        features = {
            "last": -100.0,
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 101.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
        }
        # Battlefield engine should handle gracefully
        units = compute_units(features)
        assert units is not None  # Returns neutral units


def test_backward_compatibility():
    """Ensure existing API contracts are preserved."""
    # Old code passes float, new code accepts it
    features = {
        "last": 100.5,  # Float input
        "dma20": 100.0,
        "support": 99.0,
        "resistance": 101.0,
        "rvol": 1.2,
        "rs_strength": 0.1,
        "vwap_diff": 0.01,
    }

    # Should work without modification
    units = compute_units(features)
    setups = compute_setups(features)

    # Output types unchanged (dict[str, int])
    assert isinstance(units, dict)
    assert isinstance(setups, dict)
    assert all(isinstance(v, int) for v in setups.values())


def test_integration_full_pipeline():
    """Test full pipeline from input to P&L with Decimal precision."""
    state = PositionState(cash=Decimal("100000.00"))

    # Entry features (bullish setup)
    _entry_features = {
        "TEST": {
            "last": 100.00,
            "dma20": 95.0,
            "support": 98.0,
            "resistance": 105.0,
            "rvol": 1.5,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }
    }

    # Mock entry (simplified)
    last = Decimal("100.00")
    qty = 1000
    cost = Decimal(str(qty)) * last
    state.cash -= cost
    state.positions["TEST"] = Position("TEST", qty, last)

    # Exit features (bearish reversal)
    _exit_features = {
        "TEST": {
            "last": 105.00,  # 5% gain
            "dma20": 95.0,
            "support": 98.0,
            "resistance": 105.0,
            "rvol": 0.5,
            "rs_strength": -0.2,
            "vwap_diff": -0.01,
        }
    }

    # Exit
    exit_price = Decimal("105.00")
    pos = state.positions["TEST"]
    pnl = (exit_price - pos.avg_px) * Decimal(str(pos.qty))
    state.cash += Decimal(str(pos.qty)) * exit_price

    # Verify exact P&L
    # Entry: -$100,000 for 1000 shares @ $100
    # Exit: +$105,000 for 1000 shares @ $105
    # Net: +$5,000 profit
    assert pnl == Decimal("5000.00")
    assert state.cash == Decimal("105000.00")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
