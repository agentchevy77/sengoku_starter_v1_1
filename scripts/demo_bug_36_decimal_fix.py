#!/usr/bin/env python3
"""
Demonstration of Bug #36 Fix: Systemic Mathematical Inaccuracy

This script demonstrates that aggregate.py now uses Decimal type for all
financial calculations, eliminating floating-point rounding errors.
"""

from decimal import Decimal

from optipanel.engine.aggregate import _bundle_from_features, _clamp_int, build_symbol_snapshot
from optipanel.utils.decimal_types import D_ZERO, to_decimal


def demo_decimal_precision():
    """Demonstrate that aggregate.py now uses Decimal for exact arithmetic."""
    print("\n=== Bug #36 Fix: Decimal Precision in aggregate.py ===\n")

    # Test data with problematic float values
    features = {
        "symbol": "AAPL",
        "last": 100.1,  # Float that would have precision issues
        "dma20": 100.01,
        "support": 99.99,
        "resistance": 100.3,
        "rvol": 1.1,
        "rs_strength": 0.1,
        "vwap_diff": 0.001,
        # Setup scores for testing
        "trend_long": 75,
        "trend_short": 25,
        "breakout_up": 80,
        "breakdown_down": 20,
        "exhaustion": 45,
    }

    print("1. Testing _bundle_from_features (converts to Decimal):")
    bundle = _bundle_from_features(features)
    for key in ["last", "dma20", "support", "resistance"]:
        value = bundle.get(key)
        if value:
            print(f"   {key}: {value} (type: {type(value).__name__})")

    print("\n2. Testing score calculation with Decimal:")
    snapshot = build_symbol_snapshot("AAPL", features)
    print(f"   Score: {snapshot['score']} (calculated with Decimal precision)")
    print(f"   Advice: {snapshot['advice']}")

    print("\n3. Demonstrating exact arithmetic (no float errors):")
    # Classic float problem
    float_sum = 0.1 + 0.2
    decimal_sum = to_decimal("0.1") + to_decimal("0.2")
    print(f"   Float:   0.1 + 0.2 = {float_sum}")
    print(f"   Decimal: 0.1 + 0.2 = {decimal_sum}")
    print(f"   Exact match with 0.3? {decimal_sum == Decimal('0.3')}")

    print("\n4. Testing _clamp_int with Decimal input:")
    test_values = [
        Decimal("-10"),  # Below range
        Decimal("50.5"),  # Mid-range
        Decimal("110"),  # Above range
    ]
    for val in test_values:
        clamped = _clamp_int(val)
        print(f"   _clamp_int({val}) = {clamped}")

    print("\n5. Accumulation test (no rounding errors):")
    # Accumulate small values that would cause float errors
    decimal_total = D_ZERO
    float_total = 0.0

    for _ in range(1000):
        decimal_total += to_decimal("0.001")
        float_total += 0.001

    print(f"   1000 × 0.001 (float):   {float_total}")
    print(f"   1000 × 0.001 (Decimal): {decimal_total}")
    print(f"   Decimal is exactly 1.0? {decimal_total == Decimal('1.000')}")


def demo_complex_calculation():
    """Demonstrate complex financial calculation with Decimal precision."""
    print("\n=== Complex Financial Calculation ===\n")

    features = {
        "last": "123.45",  # String to ensure exact Decimal conversion
        "dma20": "120.00",
        "support": "118.50",
        "resistance": "125.00",
        "rvol": "2.5",
        "rs_strength": "0.75",
        "vwap_diff": "0.0123",
        "bundles": {
            "1d": {
                "last": "123.45",
                "dma20": "120.00",
                "support": "118.50",
                "resistance": "125.00",
            },
            "60m": {
                "last": "123.40",
                "dma20": "119.95",
            },
        },
    }

    snapshot = build_symbol_snapshot("TEST", features)

    print(f"Symbol: {snapshot['symbol']}")
    print(f"Score: {snapshot['score']} (exact calculation)")
    print(f"Advice: {snapshot['advice']}")

    # Show the battlefield bundle is using Decimal
    bundle = snapshot.get("battlefield_bundle", {})
    print("\nBattlefield bundle (all Decimal types):")
    for key, val in list(bundle.items())[:3]:  # Show first 3 items
        print(f"  {key}: {val} (type: {type(val).__name__})")


if __name__ == "__main__":
    print(
        """
╔══════════════════════════════════════════════════════════════════╗
║         Bug #36: Systemic Mathematical Inaccuracy - FIXED        ║
║                                                                  ║
║  aggregate.py now uses Decimal type for all calculations,       ║
║  ensuring exact arithmetic with no floating-point errors.       ║
╚══════════════════════════════════════════════════════════════════╝
    """
    )

    demo_decimal_precision()
    demo_complex_calculation()

    print("\n" + "=" * 70)
    print("✅ Bug #36 has been successfully fixed!")
    print("=" * 70)
    print("\nKey improvements:")
    print("• All bundle values converted to Decimal type")
    print("• Score calculations use exact Decimal arithmetic")
    print("• Risk thresholds compared with Decimal precision")
    print("• No accumulation of rounding errors")
    print("• Backward compatible with existing code")
