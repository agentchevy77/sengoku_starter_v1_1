"""
Test Bug #27: Crash Risk from Unvalidated "Advice" Field

This test suite validates that the scan engine properly handles:
1. Standard advice values (attack, defend, standby)
2. Unexpected advice values from upstream
3. Missing advice fields
4. Missing score fields
5. Edge cases in data processing
"""

import unittest
from unittest.mock import patch

from optipanel.engine.scan import run_local_scan


class TestBug27AdviceValidation(unittest.TestCase):
    """Test suite for Bug #27 - Advice field validation in scan engine."""

    def setUp(self):
        """Set up test fixtures."""
        # Standard test data with expected advice values
        self.standard_features = {
            "AAPL": {
                "last": 150.0,
                "dma20": 145.0,
                "support": 140.0,
                "resistance": 155.0,
                "rvol": 1.5,
                "rs_strength": 0.75,
                "vwap_diff": 0.01,
            },
            "GOOGL": {
                "last": 2800.0,
                "dma20": 2750.0,
                "support": 2700.0,
                "resistance": 2850.0,
                "rvol": 1.2,
                "rs_strength": -0.5,
                "vwap_diff": -0.02,
            },
            "MSFT": {
                "last": 350.0,
                "dma20": 350.0,
                "support": 340.0,
                "resistance": 360.0,
                "rvol": 1.0,
                "rs_strength": 0.0,
                "vwap_diff": 0.0,
            },
        }

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_standard_advice_values(self, mock_build_snapshot):
        """Test that standard advice values work correctly."""
        # Mock snapshots with standard advice values
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL", "score": 30, "advice": "defend"},
            {"symbol": "MSFT", "score": 50, "advice": "standby"},
        ]

        result = run_local_scan(self.standard_features)

        # Verify advice counts
        self.assertEqual(result["advice_counts"]["attack"], 1)
        self.assertEqual(result["advice_counts"]["defend"], 1)
        self.assertEqual(result["advice_counts"]["standby"], 1)

        # Verify top ranking
        self.assertEqual(result["top"], ["AAPL", "MSFT", "GOOGL"])

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_unexpected_advice_value(self, mock_build_snapshot):
        """Test that unexpected advice values don't cause crashes."""
        # Mock snapshots with an unexpected advice value
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL", "score": 30, "advice": "hold"},  # Unexpected!
            {"symbol": "MSFT", "score": 50, "advice": "standby"},
        ]

        # This should NOT raise a KeyError
        result = run_local_scan(self.standard_features)

        # Verify advice counts include the new advice type
        self.assertEqual(result["advice_counts"]["attack"], 1)
        self.assertEqual(result["advice_counts"]["standby"], 1)
        self.assertEqual(result["advice_counts"]["hold"], 1)  # New type tracked
        self.assertEqual(result["advice_counts"]["defend"], 0)  # Not present

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_missing_advice_field(self, mock_build_snapshot):
        """Test that missing advice fields are handled gracefully."""
        # Mock snapshots with a missing advice field
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL", "score": 30},  # Missing advice field!
            {"symbol": "MSFT", "score": 50, "advice": "standby"},
        ]

        result = run_local_scan(self.standard_features)

        # Missing advice should default to "standby"
        self.assertEqual(result["advice_counts"]["attack"], 1)
        self.assertEqual(result["advice_counts"]["standby"], 2)  # MSFT + GOOGL (defaulted)
        self.assertEqual(result["advice_counts"]["defend"], 0)

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_missing_score_field(self, mock_build_snapshot):
        """Test that missing score fields are handled gracefully."""
        # Mock snapshots with a missing score field
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL", "advice": "defend"},  # Missing score field!
            {"symbol": "MSFT", "score": 50, "advice": "standby"},
        ]

        # This should NOT raise a KeyError
        result = run_local_scan(self.standard_features)

        # GOOGL with missing score (default 0) should be last
        self.assertEqual(result["top"], ["AAPL", "MSFT", "GOOGL"])

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_all_edge_cases_combined(self, mock_build_snapshot):
        """Test multiple edge cases occurring simultaneously."""
        # Mock snapshots with various edge cases
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL"},  # Missing both score and advice!
            {"symbol": "MSFT", "score": 50, "advice": "custom_advice"},  # Custom advice
            {"symbol": "TSLA", "score": 80, "advice": "attack"},
            {"symbol": "AMZN", "advice": "defend"},  # Missing score
        ]

        features = {**self.standard_features, "TSLA": {}, "AMZN": {}}

        result = run_local_scan(features)

        # Verify all advice types are tracked
        self.assertEqual(result["advice_counts"]["attack"], 2)  # AAPL, TSLA
        self.assertEqual(result["advice_counts"]["defend"], 1)  # AMZN
        self.assertEqual(result["advice_counts"]["standby"], 1)  # GOOGL (defaulted)
        self.assertEqual(result["advice_counts"]["custom_advice"], 1)  # MSFT

        # Verify ranking with default scores
        # TSLA (80), AAPL (70), MSFT (50), AMZN (0), GOOGL (0)
        # When scores are equal, stable sort preserves input order (which was alphabetical)
        # AMZN comes before GOOGL alphabetically, but GOOGL was processed before AMZN
        self.assertEqual(result["top"], ["TSLA", "AAPL", "MSFT", "GOOGL", "AMZN"])

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_empty_input(self, mock_build_snapshot):
        """Test that empty input is handled correctly."""
        result = run_local_scan({})

        self.assertEqual(result["results"], [])
        self.assertEqual(result["advice_counts"], {"attack": 0, "defend": 0, "standby": 0})
        self.assertEqual(result["top"], [])

        # build_symbol_snapshot should not be called for empty input
        mock_build_snapshot.assert_not_called()

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_advice_type_evolution(self, mock_build_snapshot):
        """Test that the system can handle evolving advice types over time."""
        # Simulate a system that starts with standard advice types
        # then evolves to include new types
        mock_build_snapshot.side_effect = [
            {"symbol": "AAPL", "score": 70, "advice": "attack"},
            {"symbol": "GOOGL", "score": 60, "advice": "accumulate"},  # New type!
            {"symbol": "MSFT", "score": 40, "advice": "distribute"},  # Another new type!
            {"symbol": "TSLA", "score": 30, "advice": "defend"},
        ]

        features = {
            "AAPL": {},
            "GOOGL": {},
            "MSFT": {},
            "TSLA": {},
        }

        result = run_local_scan(features)

        # All advice types should be tracked, including new ones
        expected_counts = {
            "attack": 1,
            "defend": 1,
            "standby": 0,
            "accumulate": 1,
            "distribute": 1,
        }

        for advice_type, count in expected_counts.items():
            self.assertEqual(
                result["advice_counts"].get(advice_type, 0),
                count,
                f"Advice type '{advice_type}' count mismatch",
            )

    def test_integration_with_real_snapshot_builder(self):
        """Integration test with real build_symbol_snapshot function."""
        # This test uses the actual build_symbol_snapshot function
        # to ensure our fix works with real data flow
        result = run_local_scan(self.standard_features)

        # Verify structure
        self.assertIn("results", result)
        self.assertIn("advice_counts", result)
        self.assertIn("top", result)

        # Verify advice_counts has at least the standard types
        for advice_type in ["attack", "defend", "standby"]:
            self.assertIn(advice_type, result["advice_counts"])

        # Verify results match input symbols
        result_symbols = {r["symbol"] for r in result["results"]}
        self.assertEqual(result_symbols, set(self.standard_features.keys()))

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_numeric_score_edge_cases(self, mock_build_snapshot):
        """Test edge cases with numeric scores."""
        mock_build_snapshot.side_effect = [
            {"symbol": "A", "score": float("inf"), "advice": "attack"},  # Infinity
            {"symbol": "B", "score": float("-inf"), "advice": "defend"},  # Negative infinity
            {"symbol": "C", "score": float("nan"), "advice": "standby"},  # NaN
            {"symbol": "D", "score": 100, "advice": "attack"},
            {"symbol": "E", "score": -100, "advice": "defend"},
        ]

        features = {f: {} for f in ["A", "B", "C", "D", "E"]}

        # The sorting should handle these edge cases without crashing
        result = run_local_scan(features)

        # Verify all symbols are in results
        self.assertEqual(len(result["results"]), 5)
        self.assertEqual(len(result["top"]), 5)

        # Verify advice counts
        self.assertEqual(result["advice_counts"]["attack"], 2)
        self.assertEqual(result["advice_counts"]["defend"], 2)
        self.assertEqual(result["advice_counts"]["standby"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
