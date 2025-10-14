#!/usr/bin/env python3
"""
Masterclass Test Suite for Bugs #27 and #28
============================================

Bug #27: Crash Risk from Unvalidated "Advice" Field
Bug #28: Crash Risk from Missing "Score" Field

This comprehensive test suite validates that both bugs are properly fixed
and the scan engine handles all edge cases gracefully without crashes.

Author: Elite Debugger
Date: 2025-10-03
"""

import unittest
from unittest.mock import patch

from optipanel.engine.scan import run_local_scan


class TestBugs27And28MasterclassFix(unittest.TestCase):
    """Masterclass test suite validating fixes for Bugs #27 and #28."""

    def setUp(self):
        """Set up test fixtures for all tests."""
        self.base_features = {
            "AAPL": {"last": 150.0, "dma20": 145.0},
            "GOOGL": {"last": 2800.0, "dma20": 2750.0},
            "MSFT": {"last": 350.0, "dma20": 350.0},
        }

    # ===== BUG #27 TESTS: Unvalidated Advice Field =====

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug27_keyerror_prevention(self, mock_build):
        """Bug #27: Verify KeyError is prevented for unknown advice types."""
        # Before fix: This would raise KeyError when counting advice
        mock_build.side_effect = [
            {"symbol": "AAPL", "score": 80, "advice": "ultra_aggressive"},  # Unknown type
            {"symbol": "GOOGL", "score": 60, "advice": "super_defensive"},  # Unknown type
            {"symbol": "MSFT", "score": 40, "advice": "neutral"},  # Unknown type
        ]

        # This must NOT raise KeyError
        result = run_local_scan(self.base_features)

        # Verify all unknown advice types are properly counted
        self.assertEqual(result["advice_counts"]["ultra_aggressive"], 1)
        self.assertEqual(result["advice_counts"]["super_defensive"], 1)
        self.assertEqual(result["advice_counts"]["neutral"], 1)
        # Standard types should still be initialized
        self.assertEqual(result["advice_counts"]["attack"], 0)
        self.assertEqual(result["advice_counts"]["defend"], 0)
        self.assertEqual(result["advice_counts"]["standby"], 0)

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug27_missing_advice_fallback(self, mock_build):
        """Bug #27: Verify missing advice fields default to 'standby'."""
        mock_build.side_effect = [
            {"symbol": "AAPL", "score": 70},  # No advice field
            {"symbol": "GOOGL", "score": 50},  # No advice field
            {"symbol": "MSFT", "score": 30, "advice": "attack"},
        ]

        result = run_local_scan(self.base_features)

        # Missing advice should default to "standby" (2 symbols)
        self.assertEqual(result["advice_counts"]["standby"], 2)
        self.assertEqual(result["advice_counts"]["attack"], 1)
        self.assertEqual(result["advice_counts"]["defend"], 0)

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug27_null_advice_handling(self, mock_build):
        """Bug #27: Verify null advice values are handled gracefully."""
        mock_build.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": None},  # Null advice
            {"symbol": "GOOGL", "score": 50, "advice": ""},  # Empty string
            {"symbol": "MSFT", "score": 30, "advice": "attack"},
        ]

        result = run_local_scan(self.base_features)

        # None and empty string should be counted as distinct advice types
        self.assertEqual(result["advice_counts"].get(None, 0), 1)
        self.assertEqual(result["advice_counts"].get("", 0), 1)
        self.assertEqual(result["advice_counts"]["attack"], 1)

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug27_mixed_advice_types(self, mock_build):
        """Bug #27: Verify system handles mix of known and unknown advice types."""
        # Create a large variety of advice types
        advice_types = [
            "attack",
            "defend",
            "standby",  # Standard
            "buy",
            "sell",
            "hold",  # Trading
            "accumulate",
            "distribute",  # Portfolio
            "🚀",
            "🛡️",
            "⏸️",  # Emoji advice
            "ATTACK",
            "Defend",
            "StandBy",  # Case variations
        ]

        snapshots = []
        for i, symbol in enumerate([f"SYM{j:03d}" for j in range(len(advice_types))]):
            snapshots.append({"symbol": symbol, "score": 100 - i, "advice": advice_types[i]})

        mock_build.side_effect = snapshots
        features = {s["symbol"]: {} for s in snapshots}

        result = run_local_scan(features)

        # All advice types should be counted
        for advice in advice_types:
            self.assertEqual(result["advice_counts"].get(advice, 0), 1, f"Advice type '{advice}' not properly counted")

    # ===== BUG #28 TESTS: Missing Score Field =====

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug28_keyerror_prevention(self, mock_build):
        """Bug #28: Verify KeyError is prevented when score field is missing."""
        # Before fix: This would raise KeyError in the lambda sort key
        mock_build.side_effect = [
            {"symbol": "AAPL", "advice": "attack"},  # No score field!
            {"symbol": "GOOGL", "advice": "defend"},  # No score field!
            {"symbol": "MSFT", "advice": "standby"},  # No score field!
        ]

        # This must NOT raise KeyError
        result = run_local_scan(self.base_features)

        # All symbols should be in the top list (with default score of 0)
        self.assertEqual(len(result["top"]), 3)
        self.assertIn("AAPL", result["top"])
        self.assertIn("GOOGL", result["top"])
        self.assertIn("MSFT", result["top"])

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug28_mixed_score_presence(self, mock_build):
        """Bug #28: Verify sorting works with mixed score presence."""
        mock_build.side_effect = [
            {"symbol": "HIGH", "score": 100, "advice": "attack"},
            {"symbol": "MID", "score": 50, "advice": "standby"},
            {"symbol": "NONE1", "advice": "defend"},  # Missing score (defaults to 0)
            {"symbol": "LOW", "score": -10, "advice": "defend"},
            {"symbol": "NONE2", "advice": "standby"},  # Missing score (defaults to 0)
        ]

        features = {s: {} for s in ["HIGH", "MID", "NONE1", "LOW", "NONE2"]}
        result = run_local_scan(features)

        # Expected order: HIGH(100), MID(50), NONE1(0), NONE2(0), LOW(-10)
        self.assertEqual(result["top"][0], "HIGH")
        self.assertEqual(result["top"][1], "MID")
        self.assertEqual(result["top"][-1], "LOW")

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug28_score_type_variations(self, mock_build):
        """Bug #28: Verify various score data types are handled."""
        mock_build.side_effect = [
            {"symbol": "INT", "score": 100, "advice": "attack"},
            {"symbol": "FLOAT", "score": 99.99, "advice": "attack"},
            {"symbol": "STR_NUM", "score": "98", "advice": "attack"},  # String number
            {"symbol": "NEGATIVE", "score": -50, "advice": "defend"},
            {"symbol": "ZERO", "score": 0, "advice": "standby"},
            {"symbol": "NONE", "score": None, "advice": "standby"},  # Null score
            {"symbol": "MISSING", "advice": "standby"},  # Missing score
        ]

        features = {s: {} for s in ["INT", "FLOAT", "STR_NUM", "NEGATIVE", "ZERO", "NONE", "MISSING"]}

        # Should handle all types without crashing
        result = run_local_scan(features)

        self.assertEqual(len(result["top"]), 7)
        # Verify highest scores are first
        self.assertEqual(result["top"][0], "INT")

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_bug28_extreme_score_values(self, mock_build):
        """Bug #28: Verify extreme numeric values don't cause crashes."""
        mock_build.side_effect = [
            {"symbol": "INF", "score": float("inf"), "advice": "attack"},
            {"symbol": "NEG_INF", "score": float("-inf"), "advice": "defend"},
            {"symbol": "NAN", "score": float("nan"), "advice": "standby"},
            {"symbol": "HUGE", "score": 1e308, "advice": "attack"},
            {"symbol": "TINY", "score": 1e-308, "advice": "standby"},
            {"symbol": "NORMAL", "score": 50, "advice": "attack"},
        ]

        features = {s: {} for s in ["INF", "NEG_INF", "NAN", "HUGE", "TINY", "NORMAL"]}

        # Must handle extreme values without crashing
        result = run_local_scan(features)

        self.assertEqual(len(result["top"]), 6)
        # Verify all symbols are present
        for symbol in features:
            self.assertIn(symbol, result["top"])

    # ===== COMBINED BUG TESTS =====

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_both_bugs_worst_case(self, mock_build):
        """Test worst-case scenario: Both missing advice AND missing score."""
        mock_build.side_effect = [
            {"symbol": "COMPLETE", "score": 100, "advice": "attack"},
            {"symbol": "NO_ADVICE", "score": 80},  # Missing advice
            {"symbol": "NO_SCORE", "advice": "defend"},  # Missing score
            {"symbol": "NOTHING"},  # Missing both!
            {"symbol": "UNKNOWN", "score": 40, "advice": "mystery"},  # Unknown advice
        ]

        features = {s: {} for s in ["COMPLETE", "NO_ADVICE", "NO_SCORE", "NOTHING", "UNKNOWN"]}

        # Must handle all edge cases without any crashes
        result = run_local_scan(features)

        # Verify all symbols processed
        self.assertEqual(len(result["results"]), 5)
        self.assertEqual(len(result["top"]), 5)

        # Verify advice counts
        self.assertIn("attack", result["advice_counts"])
        self.assertIn("defend", result["advice_counts"])
        self.assertIn("standby", result["advice_counts"])
        self.assertIn("mystery", result["advice_counts"])

        # Verify ranking (COMPLETE=100, NO_ADVICE=80, UNKNOWN=40, others=0)
        self.assertEqual(result["top"][0], "COMPLETE")
        self.assertEqual(result["top"][1], "NO_ADVICE")
        self.assertEqual(result["top"][2], "UNKNOWN")

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_production_simulation(self, mock_build):
        """Simulate production scenario with realistic data variations."""
        # Simulate production data with various edge cases that might occur
        snapshots = [
            # Normal cases
            {"symbol": "AAPL", "score": 85.5, "advice": "attack"},
            {"symbol": "GOOGL", "score": 72.3, "advice": "attack"},
            {"symbol": "MSFT", "score": 68.9, "advice": "standby"},
            # Edge cases that caused crashes
            {"symbol": "TSLA", "score": 91.2, "advice": "aggressive_buy"},  # Bug #27
            {"symbol": "AMZN"},  # Bug #27 & #28 combined
            # Data quality issues
            {"symbol": "META", "score": "55.5", "advice": "defend"},  # String score
            {"symbol": "NVDA", "score": None, "advice": None},  # Nulls
            # Upstream system errors
            {"symbol": "SPY", "error": "Connection timeout"},  # Has error field
            {"symbol": "QQQ", "score": 0, "advice": ""},  # Empty advice
        ]

        mock_build.side_effect = snapshots
        features = {s["symbol"]: {} for s in snapshots}

        # Production code must handle all these cases gracefully
        result = run_local_scan(features)

        # Verify no crash and all symbols processed
        self.assertEqual(len(result["results"]), 9)
        self.assertEqual(len(result["top"]), 9)

        # Verify advice counting works with all variations
        self.assertGreater(sum(result["advice_counts"].values()), 0)

        # Verify top list is properly sorted
        top_symbols = result["top"]
        # TSLA should be first (highest score)
        self.assertEqual(top_symbols[0], "TSLA")

    def test_performance_with_large_dataset(self):
        """Verify fixes don't degrade performance with large datasets."""
        import time

        # Create large dataset with edge cases
        large_features = {}
        for i in range(1000):
            large_features[f"SYM{i:04d}"] = {
                "last": 100.0 + i,
                "dma20": 95.0 + i,
            }

        # Add problematic entries
        large_features["MISSING_BOTH"] = {}
        large_features["WEIRD_DATA"] = {"score": "not_a_number", "advice": 123}

        start_time = time.time()
        result = run_local_scan(large_features)
        elapsed = time.time() - start_time

        # Should complete in reasonable time even with edge cases
        self.assertLess(elapsed, 5.0, f"Performance degraded: {elapsed:.2f}s for 1000 symbols")

        # Verify all symbols processed
        self.assertEqual(len(result["results"]), 1002)
        self.assertEqual(len(result["top"]), 1002)

    def test_backwards_compatibility(self):
        """Verify fixes maintain backwards compatibility with existing code."""
        # Test with standard features that existing code expects
        result = run_local_scan(self.base_features)

        # Verify expected structure
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIn("advice_counts", result)
        self.assertIn("top", result)

        # Verify advice_counts always has standard types
        for advice_type in ["attack", "defend", "standby"]:
            self.assertIn(advice_type, result["advice_counts"])
            self.assertIsInstance(result["advice_counts"][advice_type], int)

        # Verify results structure
        self.assertIsInstance(result["results"], list)
        for r in result["results"]:
            self.assertIsInstance(r, dict)
            self.assertIn("symbol", r)

        # Verify top is list of strings
        self.assertIsInstance(result["top"], list)
        for symbol in result["top"]:
            self.assertIsInstance(symbol, str)


class TestBugFixDocumentation(unittest.TestCase):
    """Test that documents the bugs and verifies fixes are in place."""

    def test_bug_27_documentation(self):
        """Document Bug #27 and verify fix implementation."""
        # Bug #27: Crash Risk from Unvalidated "Advice" Field
        # Location: optipanel/engine/scan.py
        # Problem: Code assumed advice would only be "attack", "defend", or "standby"
        # Fix: Use advice_counts.get(advice, 0) instead of direct access

        # Read the actual implementation
        import inspect

        from optipanel.engine import scan

        source = inspect.getsource(scan.run_local_scan)

        # Verify the fix is in place
        self.assertIn(".get(", source, "Bug #27 fix: Should use .get() for safe access")
        self.assertIn('r.get("advice"', source, "Should safely get advice field")
        self.assertIn("advice_counts.get(advice", source, "Should safely increment counts")

    def test_bug_28_documentation(self):
        """Document Bug #28 and verify fix implementation."""
        # Bug #28: Crash Risk from Missing "Score" Field
        # Location: optipanel/engine/scan.py
        # Problem: Lambda in sorted() would raise KeyError if score was missing
        # Fix: Use safe_score function that handles missing/None/string scores

        import inspect

        from optipanel.engine import scan

        source = inspect.getsource(scan.run_local_scan)

        # Verify the fix is in place - we now use a safe_score function
        self.assertIn("def safe_score", source, "Bug #28 fix: Should have safe_score function")
        self.assertIn('.get("score"', source, "Bug #28 fix: Should safely get score field")
        self.assertIn("float(score)", source, "Should convert score to float for type safety")


if __name__ == "__main__":
    # Run with verbose output to show all test results
    unittest.main(verbosity=2)
