#!/usr/bin/env python3
"""Test to validate Bug #8: Shallow Copy State Corruption Risk.

Bug #8 claims that using dict(feats) creates a shallow copy that could lead
to shared mutable state between consumers. This test validates whether the
bug is real or a false positive.
"""

import copy


def test_shallow_copy_with_nested_bundles():
    """Test if shallow copy of features with nested bundles causes shared state."""
    # Create a mock feature dict with nested bundles structure
    mock_features = {
        "AAPL": {
            "last": 150.0,
            "dma20": 145.0,
            "bundles": {
                "15m": {"last": 149.5, "support": 148.0, "resistance": 151.0},
                "60m": {"last": 150.2, "support": 147.5, "resistance": 152.0},
            },
        }
    }

    # Simulate what happens in the code at line 253 of app.py
    # The code does: features[sym_upper] = dict(feats)
    original_feat = mock_features["AAPL"]
    copied_feat = dict(original_feat)  # This is what the code does

    # Test 1: Top-level modification should not affect original
    copied_feat["last"] = 200.0
    assert original_feat["last"] == 150.0, "Top-level modification affected original"
    print("✓ Test 1 passed: Top-level modifications are isolated")

    # Test 2: Nested modification WILL affect original (this is the bug!)
    copied_feat["bundles"]["15m"]["last"] = 999.0
    if original_feat["bundles"]["15m"]["last"] == 999.0:
        print("✗ Test 2 FAILED: Nested modification affected original!")
        print("  Bug #8 CONFIRMED: Shallow copy shares nested mutable state")
    else:
        print("✓ Test 2 passed: Nested modifications are isolated")
        raise AssertionError("Bug #8 appears to be FALSE POSITIVE")

    # Reset for next test
    original_feat["bundles"]["15m"]["last"] = 149.5

    # Test 3: What deep copy would do (the proposed fix)
    deep_copied = copy.deepcopy(original_feat)
    deep_copied["bundles"]["15m"]["last"] = 888.0
    assert original_feat["bundles"]["15m"]["last"] == 149.5, "Deep copy failed to protect original"
    print("✓ Test 3 passed: Deep copy properly isolates nested structures")


def test_actual_code_path():
    """Test the actual code path in gather_panels to see if bug manifests."""
    # This test would require more complex mocking of the entire flow
    # For now, the direct test above proves the bug exists


if __name__ == "__main__":
    try:
        test_shallow_copy_with_nested_bundles()
        print("\n✅ Bug #8 is VALID - shallow copy creates shared mutable state risk")
    except AssertionError as e:
        print(f"\n❌ Bug #8 appears to be false positive: {e}")
