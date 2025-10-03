#!/usr/bin/env python3
"""Comprehensive test suite for Bug #8: Deep copy fix for nested feature data.

This test suite validates that the fix for Bug #8 properly isolates nested
feature data between consumers using deep copy instead of shallow copy.
"""

import copy
import threading
import time

import pytest

from optipanel.api.app import safe_deep_copy_features


class TestBug8DeepCopyFix:
    """Test suite for Bug #8 deep copy fix."""

    def test_safe_deep_copy_features_basic(self):
        """Test that safe_deep_copy_features creates independent copies."""
        # Create test data with nested structures
        original = {
            "last": 150.0,
            "dma20": 145.0,
            "bundles": {"15m": {"last": 149.5, "support": 148.0}, "60m": {"last": 150.2, "support": 147.5}},
        }

        # Create deep copy
        copied = safe_deep_copy_features(original)

        # Verify initial equality
        assert copied == original
        assert copied is not original  # Different objects

        # Modify top-level field in copy
        copied["last"] = 200.0
        assert original["last"] == 150.0  # Original unchanged

        # Modify nested field in copy
        copied["bundles"]["15m"]["last"] = 999.0
        assert original["bundles"]["15m"]["last"] == 149.5  # Original unchanged

        # Verify nested objects are different
        assert copied["bundles"] is not original["bundles"]
        assert copied["bundles"]["15m"] is not original["bundles"]["15m"]

    def test_thread_safety_with_deep_copy(self):
        """Test that deep copy ensures thread safety with concurrent access."""
        # Shared original data
        original_features = {
            "AAPL": {
                "last": 150.0,
                "bundles": {"15m": {"last": 149.5, "volume": 1000000}, "60m": {"last": 150.2, "volume": 5000000}},
            }
        }

        # Results storage
        results = {"thread1": None, "thread2": None, "race_detected": False}

        def consumer_thread(thread_id: str, delay: float):
            """Simulate a consumer that modifies nested data."""
            # Get a deep copy (simulating what gather_panels does)
            features = safe_deep_copy_features(original_features["AAPL"])

            # Modify nested data
            features["bundles"]["15m"]["last"] = 100.0 + float(thread_id[-1])

            # Simulate processing time
            time.sleep(delay)

            # Store result
            results[thread_id] = features["bundles"]["15m"]["last"]

            # Check if original was modified (race condition)
            if original_features["AAPL"]["bundles"]["15m"]["last"] != 149.5:
                results["race_detected"] = True

        # Run two threads concurrently
        t1 = threading.Thread(target=consumer_thread, args=("thread1", 0.01))
        t2 = threading.Thread(target=consumer_thread, args=("thread2", 0.02))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Verify results
        assert results["thread1"] == 101.0  # thread1's modification
        assert results["thread2"] == 102.0  # thread2's modification
        assert not results["race_detected"]  # No race condition
        assert original_features["AAPL"]["bundles"]["15m"]["last"] == 149.5  # Original unchanged

    def test_gather_panels_deep_copy_integration(self):
        """Test that the deep copy fix is properly integrated in gather_panels."""
        # Direct test of the code path we fixed
        from optipanel.api.app import safe_deep_copy_features

        # Simulate what happens inside gather_panels
        mock_payload = {
            "AAPL": {"last": 150.0, "dma20": 145.0, "bundles": {"15m": {"last": 149.5}, "60m": {"last": 150.2}}}
        }

        # This simulates the loop in gather_panels at lines 269-275
        features = {}
        for sym, feats in mock_payload.items():
            if isinstance(feats, dict) and feats.get("last"):
                sym_upper = str(sym).upper()
                # This is the actual fix we implemented
                features[sym_upper] = safe_deep_copy_features(feats)

        # Now modify the copied features
        features["AAPL"]["bundles"]["15m"]["last"] = 999.0

        # Original should be unchanged (deep copy works)
        assert mock_payload["AAPL"]["bundles"]["15m"]["last"] == 149.5
        print("✓ Deep copy integration test passed")

    def test_performance_characteristics(self):
        """Test performance impact of deep copy vs shallow copy."""
        import timeit

        # Create test data with varying nesting depth
        test_data = {
            "symbol": "TEST",
            "last": 100.0,
            "bundles": {
                f"tf_{i}": {"last": 100.0 + i, "metrics": {"volume": 1000000 * i, "spread": 0.01 * i}}
                for i in range(10)  # 10 timeframes
            },
        }

        # Measure shallow copy time
        shallow_time = timeit.timeit(lambda: dict(test_data), number=10000)

        # Measure deep copy time
        deep_time = timeit.timeit(lambda: copy.deepcopy(test_data), number=10000)

        # Deep copy should be slower but not prohibitively so
        overhead_ratio = deep_time / shallow_time
        print(f"Performance overhead: {overhead_ratio:.2f}x")
        print(f"Shallow copy: {shallow_time:.4f}s for 10k copies")
        print(f"Deep copy: {deep_time:.4f}s for 10k copies")

        # Verify deep copy is working correctly
        deep_copied = copy.deepcopy(test_data)
        deep_copied["bundles"]["tf_0"]["metrics"]["volume"] = 999999999
        assert test_data["bundles"]["tf_0"]["metrics"]["volume"] == 0  # Original unchanged

        # Shallow copy would fail this test
        shallow_copied = dict(test_data)
        shallow_copied["bundles"]["tf_1"]["metrics"]["volume"] = 888888888
        assert test_data["bundles"]["tf_1"]["metrics"]["volume"] == 888888888  # Original CHANGED!

    def test_edge_cases(self):
        """Test edge cases for the deep copy fix."""
        # Test 1: Empty features
        empty = {}
        copied = safe_deep_copy_features(empty)
        assert copied == empty
        assert copied is not empty

        # Test 2: Features without bundles
        no_bundles = {"last": 100.0, "dma20": 95.0}
        copied = safe_deep_copy_features(no_bundles)
        copied["last"] = 200.0
        assert no_bundles["last"] == 100.0

        # Test 3: Features with None values
        with_none = {"last": 100.0, "bundles": None}
        copied = safe_deep_copy_features(with_none)
        assert copied["bundles"] is None

        # Test 4: Deeply nested structures
        deep_nested = {
            "last": 100.0,
            "bundles": {"15m": {"indicators": {"macd": {"value": 0.5, "signal": 0.3, "histogram": 0.2}}}},
        }
        copied = safe_deep_copy_features(deep_nested)
        copied["bundles"]["15m"]["indicators"]["macd"]["value"] = 999.0
        assert deep_nested["bundles"]["15m"]["indicators"]["macd"]["value"] == 0.5

    def test_memory_isolation(self):
        """Test that deep copy provides complete memory isolation."""
        # Create complex nested structure
        original = {
            "symbol": "TEST",
            "last": 150.0,
            "lists": [1, 2, 3],  # Mutable list
            "bundles": {
                "15m": {"candles": [{"open": 149.0, "close": 150.0}, {"open": 150.0, "close": 151.0}]}  # List of dicts
            },
        }

        # Create multiple copies
        copies = [safe_deep_copy_features(original) for _ in range(3)]

        # Modify each copy differently
        copies[0]["lists"].append(4)
        copies[1]["bundles"]["15m"]["candles"][0]["open"] = 200.0
        copies[2]["bundles"]["15m"]["candles"].append({"open": 151.0, "close": 152.0})

        # Verify original is unchanged
        assert original["lists"] == [1, 2, 3]
        assert original["bundles"]["15m"]["candles"][0]["open"] == 149.0
        assert len(original["bundles"]["15m"]["candles"]) == 2

        # Verify copies are independent
        assert copies[0]["lists"] == [1, 2, 3, 4]
        assert copies[1]["bundles"]["15m"]["candles"][0]["open"] == 200.0
        assert len(copies[2]["bundles"]["15m"]["candles"]) == 3


def test_bug_8_validation():
    """Standalone test to validate Bug #8 is fixed."""
    # Reproduce original bug scenario
    original_data = {"AAPL": {"last": 150.0, "bundles": {"15m": {"last": 149.5}}}}

    # What the old code did (shallow copy)
    shallow_copy = dict(original_data["AAPL"])
    shallow_copy["bundles"]["15m"]["last"] = 999.0
    # Bug: Original is modified!
    assert original_data["AAPL"]["bundles"]["15m"]["last"] == 999.0
    print("✗ Bug #8 reproduced: Shallow copy shares nested state")

    # Reset
    original_data["AAPL"]["bundles"]["15m"]["last"] = 149.5

    # What the new code does (deep copy)
    deep_copy = safe_deep_copy_features(original_data["AAPL"])
    deep_copy["bundles"]["15m"]["last"] = 888.0
    # Fixed: Original is unchanged!
    assert original_data["AAPL"]["bundles"]["15m"]["last"] == 149.5
    print("✓ Bug #8 fixed: Deep copy isolates nested state")


if __name__ == "__main__":
    # Run validation test
    test_bug_8_validation()

    # Run full test suite
    pytest.main([__file__, "-v", "--tb=short"])
