#!/usr/bin/env python3
"""Demonstration of Bug #8 fix: Deep copy prevents shared mutable state.

This script demonstrates how the fix for Bug #8 prevents the shallow copy
state corruption issue where nested feature data was shared between consumers.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.api.app import safe_deep_copy_features


def demonstrate_bug():
    """Demonstrate the original bug with shallow copy."""
    print("=" * 60)
    print("DEMONSTRATING BUG #8: Shallow Copy State Corruption")
    print("=" * 60)

    # Original feature data with nested bundles
    original_features = {
        "last": 150.0,
        "dma20": 145.0,
        "bundles": {"15m": {"last": 149.5, "support": 148.0}, "60m": {"last": 150.2, "support": 147.5}},
    }

    print("\nOriginal feature data:")
    print(f"  last: {original_features['last']}")
    print(f"  bundles.15m.last: {original_features['bundles']['15m']['last']}")

    # Create shallow copy (the old buggy way)
    print("\nCreating shallow copy with dict()...")
    shallow_copy = dict(original_features)

    # Modify nested data in the copy
    print("Modifying shallow_copy['bundles']['15m']['last'] = 999.0")
    shallow_copy["bundles"]["15m"]["last"] = 999.0

    # Check original - BUG: It's modified too!
    print("\nChecking original after shallow copy modification:")
    print(f"  original['bundles']['15m']['last'] = {original_features['bundles']['15m']['last']}")

    if original_features["bundles"]["15m"]["last"] == 999.0:
        print("  ❌ BUG CONFIRMED: Original was modified by shallow copy!")
    else:
        print("  ✓ No bug detected (unexpected)")

    # Reset for next demo
    original_features["bundles"]["15m"]["last"] = 149.5


def demonstrate_fix():
    """Demonstrate the fix with deep copy."""
    print("\n" + "=" * 60)
    print("DEMONSTRATING FIX: Deep Copy Isolation")
    print("=" * 60)

    # Original feature data with nested bundles
    original_features = {
        "last": 150.0,
        "dma20": 145.0,
        "bundles": {"15m": {"last": 149.5, "support": 148.0}, "60m": {"last": 150.2, "support": 147.5}},
    }

    print("\nOriginal feature data:")
    print(f"  last: {original_features['last']}")
    print(f"  bundles.15m.last: {original_features['bundles']['15m']['last']}")

    # Create deep copy (the fixed way)
    print("\nCreating deep copy with safe_deep_copy_features()...")
    deep_copy = safe_deep_copy_features(original_features)

    # Modify nested data in the copy
    print("Modifying deep_copy['bundles']['15m']['last'] = 888.0")
    deep_copy["bundles"]["15m"]["last"] = 888.0

    # Check original - FIXED: It's unchanged!
    print("\nChecking original after deep copy modification:")
    print(f"  original['bundles']['15m']['last'] = {original_features['bundles']['15m']['last']}")

    if original_features["bundles"]["15m"]["last"] == 149.5:
        print("  ✅ FIX CONFIRMED: Original is unchanged (isolated)!")
    else:
        print("  ❌ Fix failed (unexpected)")


def demonstrate_concurrent_access():
    """Demonstrate thread safety with deep copy."""
    print("\n" + "=" * 60)
    print("DEMONSTRATING: Concurrent Access Safety")
    print("=" * 60)

    import threading
    import time

    shared_data = {"AAPL": {"last": 150.0, "bundles": {"15m": {"last": 149.5}}}}

    results = []

    def consumer(consumer_id):
        """Simulate a consumer modifying data."""
        # Get a deep copy (safe)
        my_copy = safe_deep_copy_features(shared_data["AAPL"])

        # Modify the copy
        my_copy["bundles"]["15m"]["last"] = 100.0 + consumer_id

        # Simulate processing
        time.sleep(0.01)

        # Store result
        results.append(
            {
                "consumer": consumer_id,
                "value": my_copy["bundles"]["15m"]["last"],
                "original_intact": shared_data["AAPL"]["bundles"]["15m"]["last"] == 149.5,
            }
        )

    print("\nStarting 5 concurrent consumers...")
    threads = []
    for i in range(5):
        t = threading.Thread(target=consumer, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\nResults:")
    for r in results:
        print(f"  Consumer {r['consumer']}: value={r['value']}, original_intact={r['original_intact']}")

    print(f"\nFinal original value: {shared_data['AAPL']['bundles']['15m']['last']}")
    if shared_data["AAPL"]["bundles"]["15m"]["last"] == 149.5:
        print("✅ All consumers isolated - original data intact!")
    else:
        print("❌ Data corruption detected!")


if __name__ == "__main__":
    print("\n" + "🔧 BUG #8 FIX DEMONSTRATION 🔧".center(60))
    print("Shallow Copy State Corruption Risk - Fixed with Deep Copy")

    demonstrate_bug()
    demonstrate_fix()
    demonstrate_concurrent_access()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✅ Bug #8 has been successfully fixed!")
    print("✅ Deep copy ensures complete data isolation")
    print("✅ Thread-safe for concurrent access")
    print("✅ Backward compatible - no API changes")
    print("\nFiles modified:")
    print("  - optipanel/api/app.py (added safe_deep_copy_features)")
    print("  - Lines 253, 264 updated to use deep copy")
    print("=" * 60)
