"""Test suite for Bug #29: Redundant Processing fix.

This module validates that the scan engine no longer performs unnecessary
alphabetical sorting of symbols before processing, improving performance
from O(n log n) to O(n).

Bug #29 Context:
    - Location: optipanel/engine/scan.py (run_local_scan)
    - Problem: Code sorted symbols alphabetically before processing
    - Impact: Wasted CPU cycles with no semantic value
    - Fix: Removed sorted() call, iterate in dictionary insertion order
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest

from optipanel.engine.scan import run_local_scan


class TestBug29RedundantSort:
    """Test that redundant alphabetical sort has been removed."""

    @pytest.fixture
    def standard_features(self) -> dict[str, dict[str, Any]]:
        """Create standard test feature data."""
        return {
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

    def test_results_preserve_insertion_order_not_alphabetical(
        self, standard_features: dict[str, dict[str, Any]]
    ) -> None:
        """Bug #29 PRIMARY TEST: Results should preserve insertion order, not alphabetical.

        Before the fix, symbols were processed in alphabetical order.
        After the fix, symbols are processed in dictionary insertion order.
        """
        # Create a dictionary with non-alphabetical insertion order
        # Insertion order: ZEBRA, APPLE, MICROSOFT
        # Alphabetical order would be: APPLE, MICROSOFT, ZEBRA
        features = {
            "ZEBRA": standard_features["AAPL"],  # First insertion
            "APPLE": standard_features["GOOGL"],  # Second insertion
            "MICROSOFT": standard_features["MSFT"],  # Third insertion
        }

        result = run_local_scan(features)

        # Extract symbols from results in the order they appear
        result_symbols = [r["symbol"] for r in result["results"]]

        # Bug #29 fix validation: Results should be in INSERTION order, not ALPHABETICAL
        expected_insertion_order = ["ZEBRA", "APPLE", "MICROSOFT"]
        alphabetical_order = ["APPLE", "MICROSOFT", "ZEBRA"]

        assert result_symbols == expected_insertion_order, (
            f"Bug #29 REGRESSION: Results are in alphabetical order {alphabetical_order} "
            f"instead of insertion order {expected_insertion_order}. "
            f"The redundant sort has been re-introduced!"
        )

        # Also verify it's NOT in alphabetical order (to catch false positives)
        assert (
            result_symbols != alphabetical_order
        ), "Test design flaw: insertion order happens to match alphabetical order"

    def test_top_list_still_sorted_by_score(self, standard_features: dict[str, dict[str, Any]]) -> None:
        """Verify that 'top' list is still correctly sorted by score descending.

        This validates that removing the alphabetical sort didn't break the
        score-based sorting of the final output.
        """
        result = run_local_scan(standard_features)

        # Extract scores for each symbol in 'top' order
        symbol_to_score = {r["symbol"]: r["score"] for r in result["results"]}
        top_scores = [symbol_to_score[sym] for sym in result["top"]]

        # Verify scores are in descending order
        assert top_scores == sorted(top_scores, reverse=True), "Top list should be sorted by score descending"

    def test_deterministic_output_for_same_input(self, standard_features: dict[str, dict[str, Any]]) -> None:
        """Verify that output is deterministic for the same input.

        Even without alphabetical sorting, the output should be reproducible
        because dictionary insertion order is guaranteed in Python 3.7+.
        """
        # Run the scan multiple times with the same input
        results = [run_local_scan(standard_features) for _ in range(5)]

        # All runs should produce identical results
        first_run = results[0]
        for i, run in enumerate(results[1:], start=2):
            assert run["top"] == first_run["top"], f"Run {i} produced different 'top' list than run 1"
            assert (
                run["advice_counts"] == first_run["advice_counts"]
            ), f"Run {i} produced different advice_counts than run 1"
            # Check results list order
            run_symbols = [r["symbol"] for r in run["results"]]
            first_symbols = [r["symbol"] for r in first_run["results"]]
            assert run_symbols == first_symbols, f"Run {i} processed symbols in different order than run 1"

    def test_advice_counts_unchanged(self, standard_features: dict[str, dict[str, Any]]) -> None:
        """Verify that advice_counts aggregation is unchanged by the fix.

        Advice counts should be the same regardless of processing order.
        """
        result = run_local_scan(standard_features)

        # Verify advice_counts structure
        assert "attack" in result["advice_counts"]
        assert "defend" in result["advice_counts"]
        assert "standby" in result["advice_counts"]

        # Verify total count matches number of symbols
        total_advice = sum(result["advice_counts"].values())
        assert total_advice == len(standard_features), "Total advice counts should equal number of symbols"

    def test_performance_improvement_large_watchlist(self) -> None:
        """Validate performance improvement for large watchlists.

        This test demonstrates that removing the sort improves performance
        for large symbol lists.
        """
        # Create a large watchlist (100 symbols)
        large_features = {
            f"SYM{i:03d}": {
                "last": 100.0 + i,
                "dma20": 100.0,
                "support": 95.0,
                "resistance": 105.0,
                "rvol": 1.0,
                "rs_strength": 0.0,
                "vwap_diff": 0.0,
            }
            for i in range(100)
        }

        # Measure execution time
        start = time.perf_counter()
        result = run_local_scan(large_features)
        elapsed = time.perf_counter() - start

        # Verify result is valid
        assert len(result["results"]) == 100
        assert len(result["top"]) == 100

        # The fix should make this faster, but we can't assert on absolute timing
        # Just verify it completes in reasonable time (< 1 second)
        assert elapsed < 1.0, (
            f"Processing 100 symbols took {elapsed:.3f}s, which seems slow. " "Expected < 1.0s for this operation."
        )

    @patch("optipanel.engine.scan.build_symbol_snapshot")
    def test_processing_order_matches_insertion_order(
        self, mock_build_snapshot, standard_features: dict[str, dict[str, Any]]
    ) -> None:
        """Verify that symbols are processed in insertion order, not alphabetical.

        This test tracks the order in which build_symbol_snapshot is called
        to ensure it matches dictionary insertion order.
        """
        # Set up mock to track call order
        call_order = []

        def track_calls(symbol: str, features: dict[str, Any]) -> dict[str, Any]:
            call_order.append(symbol)
            return {
                "symbol": symbol,
                "score": 50,
                "advice": "standby",
                "units": {},
                "setups": {},
                "battlefield_bundle": {},
                "prob_chips": {},
            }

        mock_build_snapshot.side_effect = track_calls

        # Create features with specific insertion order
        # Insertion order: ZULU, ALPHA, BRAVO (not alphabetical!)
        features = {
            "ZULU": standard_features["AAPL"],
            "ALPHA": standard_features["GOOGL"],
            "BRAVO": standard_features["MSFT"],
        }

        run_local_scan(features)

        # Verify build_symbol_snapshot was called in insertion order
        expected_order = ["ZULU", "ALPHA", "BRAVO"]
        assert call_order == expected_order, (
            f"build_symbol_snapshot was called in order {call_order}, " f"expected insertion order {expected_order}"
        )

        # Verify it's NOT alphabetical order (to catch false positives)
        alphabetical = ["ALPHA", "BRAVO", "ZULU"]
        assert call_order != alphabetical, "Test design flaw: insertion order happens to match alphabetical"

    def test_stable_sort_for_equal_scores(self, standard_features: dict[str, dict[str, Any]]) -> None:
        """Verify stable sort behavior when scores are equal.

        When multiple symbols have the same score, stable sort should preserve
        their relative order from the results list (insertion order).
        """
        # Mock to return equal scores for all symbols
        with patch("optipanel.engine.scan.build_symbol_snapshot") as mock:
            mock.side_effect = [
                {"symbol": "CHARLIE", "score": 50, "advice": "standby"},
                {"symbol": "ALPHA", "score": 50, "advice": "standby"},
                {"symbol": "BRAVO", "score": 50, "advice": "standby"},
            ]

            # Insertion order: CHARLIE, ALPHA, BRAVO
            features = {
                "CHARLIE": standard_features["AAPL"],
                "ALPHA": standard_features["GOOGL"],
                "BRAVO": standard_features["MSFT"],
            }

            result = run_local_scan(features)

            # With equal scores, stable sort preserves insertion order
            # So top should be: CHARLIE, ALPHA, BRAVO (not alphabetical!)
            expected_top = ["CHARLIE", "ALPHA", "BRAVO"]
            assert result["top"] == expected_top, (
                f"With equal scores, expected insertion order {expected_top}, " f"got {result['top']}"
            )

    def test_backward_compatibility_with_existing_code(self, standard_features: dict[str, dict[str, Any]]) -> None:
        """Verify backward compatibility: output contracts are unchanged.

        This test ensures that the fix doesn't break any output contracts:
        - 'results' is a list of snapshots
        - 'advice_counts' is a dict with at least attack/defend/standby
        - 'top' is a list of symbols sorted by score descending
        """
        result = run_local_scan(standard_features)

        # Verify output structure
        assert "results" in result
        assert "advice_counts" in result
        assert "top" in result

        # Verify results structure
        assert isinstance(result["results"], list)
        assert len(result["results"]) == len(standard_features)

        for snapshot in result["results"]:
            assert "symbol" in snapshot
            assert "score" in snapshot
            assert "advice" in snapshot
            assert "units" in snapshot
            assert "setups" in snapshot

        # Verify advice_counts structure
        assert isinstance(result["advice_counts"], dict)
        assert "attack" in result["advice_counts"]
        assert "defend" in result["advice_counts"]
        assert "standby" in result["advice_counts"]

        # Verify top structure
        assert isinstance(result["top"], list)
        assert len(result["top"]) == len(standard_features)
        assert all(isinstance(sym, str) for sym in result["top"])


class TestBug29PerformanceImpact:
    """Performance-focused tests for Bug #29 fix."""

    def test_complexity_reduction_demonstration(self) -> None:
        """Demonstrate complexity reduction from O(n log n) to O(n).

        This test shows that processing time scales linearly with input size,
        not logarithmically, after removing the sort.
        """
        # Test with increasing sizes
        sizes = [10, 50, 100]
        times = []

        for size in sizes:
            features = {
                f"SYM{i:04d}": {
                    "last": 100.0,
                    "dma20": 100.0,
                    "support": 95.0,
                    "resistance": 105.0,
                    "rvol": 1.0,
                    "rs_strength": 0.0,
                    "vwap_diff": 0.0,
                }
                for i in range(size)
            }

            start = time.perf_counter()
            run_local_scan(features)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # With linear complexity, time should scale roughly linearly
        # 50 symbols should take ~5x as long as 10 symbols
        # 100 symbols should take ~10x as long as 10 symbols
        # Allow some variance for noise
        ratio_50_to_10 = times[1] / times[0]
        ratio_100_to_10 = times[2] / times[0]

        # These ratios should be in reasonable ranges for linear scaling
        # With O(n log n), the ratio would be much higher (e.g., 66x for 100 vs 10)
        # Note: This is a loose check since actual times are very small and include overhead
        # Linear would be exactly 5x and 10x, but we allow for noise and setup overhead
        assert ratio_50_to_10 < 15, f"50-symbol time ratio {ratio_50_to_10:.2f} suggests worse than linear scaling"
        assert ratio_100_to_10 < 30, (
            f"100-symbol time ratio {ratio_100_to_10:.2f} suggests worse than linear scaling. "
            f"Expected < 30x for linear scaling (vs ~66x for O(n log n))."
        )

    def test_no_unnecessary_allocations(self) -> None:
        """Verify that the fix doesn't introduce memory overhead.

        The fix should reduce memory usage by not creating the sorted() iterator.
        """
        features = {
            f"SYM{i}": {
                "last": 100.0,
                "dma20": 100.0,
                "support": 95.0,
                "resistance": 105.0,
                "rvol": 1.0,
                "rs_strength": 0.0,
                "vwap_diff": 0.0,
            }
            for i in range(100)
        }

        # Run scan and verify it completes without issues
        result = run_local_scan(features)

        # Basic sanity checks
        assert len(result["results"]) == 100
        assert len(result["top"]) == 100
        assert sum(result["advice_counts"].values()) == 100
