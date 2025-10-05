"""Test suite for Bug #4: Inefficient Symbol Fetching fix.

This module validates that the reference symbol (e.g., "SPY") is only fetched
when it's actually in the requested symbols list, preventing wasteful network calls.

Bug #4 Context:
    - Location: optipanel/adapters/ibkr/tws_fetcher.py (features_for_symbols)
    - Problem: Unconditionally fetched reference symbol even when not requested
    - Impact: Wasted network call and processing time for every request
    - Fix: Conditional fetching based on whether ref is in requested symbols
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import Mock, patch

import pytest

from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig, _HistApp


class TestBug4RefSymbolFetch:
    """Test that reference symbol is only fetched when necessary."""

    @pytest.fixture
    def mock_config(self) -> TwsConfig:
        """Create a test configuration with known reference symbol."""
        return TwsConfig(
            host="127.0.0.1",
            port=7496,
            client_id=999,
            ref_symbol="SPY",  # Known reference symbol
            handshake_timeout=1.0,
            hist_timeout=5.0,
        )

    @pytest.fixture
    def fetcher(self, mock_config: TwsConfig) -> RealTwsFetcher:
        """Create a fetcher instance with mock config."""
        return RealTwsFetcher(cfg=mock_config)

    @pytest.fixture
    def mock_app(self) -> Mock:
        """Create a mock TWS application for testing."""
        app = Mock(spec=_HistApp)
        app.errors = []
        app.ready = threading.Event()
        app.ready.set()
        app.cleanup = Mock()

        # Mock the register_request method
        def register_request_mock(req_id: int) -> threading.Event:
            evt = threading.Event()
            evt.set()  # Immediately ready
            return evt

        app.register_request = Mock(side_effect=register_request_mock)
        app.take_bars = Mock(
            return_value=[
                ("20240101", 100.0, 105.0, 99.0, 104.0, 1000000),
                ("20240102", 104.0, 106.0, 103.0, 105.0, 1100000),
            ]
        )
        app.release = Mock()
        app.reqHistoricalData = Mock()

        return app

    def test_ref_symbol_not_fetched_when_not_requested(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Bug #4 PRIMARY TEST: Ref symbol should NOT be fetched if not in request.

        This is the core test validating the fix. Before the fix, "SPY" would
        always be fetched. After the fix, it's only fetched if requested.
        """
        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            # Request symbols that DO NOT include the ref symbol "SPY"
            result = fetcher.features_for_symbols(["AAPL", "MSFT", "GOOGL"])

            # Verify the results contain the requested symbols
            assert set(result.keys()) == {"AAPL", "MSFT", "GOOGL"}

            # CRITICAL ASSERTION: _fetch_daily should NOT be called for "SPY"
            # Extract all symbols that were fetched
            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]

            # Bug #4 fix validation: SPY should NOT be in fetched symbols
            assert "SPY" not in fetched_symbols, (
                "Bug #4 REGRESSION: Reference symbol 'SPY' was fetched even though "
                "it was not in the requested symbols list. This wastes a network call."
            )

            # Verify only requested symbols were fetched
            assert set(fetched_symbols) == {"AAPL", "MSFT", "GOOGL"}

            # Verify exactly 3 fetches (not 4 with SPY)
            assert mock_fetch.call_count == 3

    def test_ref_symbol_fetched_when_requested(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Ref symbol SHOULD be fetched when explicitly requested.

        This validates backward compatibility: when the ref symbol is in the
        requested list, it should still be fetched (and fetched first for
        rs_strength calculations).
        """
        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            # Request symbols that DO include the ref symbol "SPY"
            result = fetcher.features_for_symbols(["AAPL", "SPY", "MSFT"])

            # Verify the results contain all requested symbols
            assert set(result.keys()) == {"AAPL", "SPY", "MSFT"}

            # Extract fetched symbols in order
            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]

            # Verify SPY was fetched
            assert "SPY" in fetched_symbols

            # Verify SPY was fetched FIRST (for rs_strength calculation)
            assert fetched_symbols[0] == "SPY", (
                "Reference symbol should be fetched first when requested "
                "to enable rs_strength calculation for other symbols"
            )

            # Verify all requested symbols were fetched
            assert set(fetched_symbols) == {"AAPL", "SPY", "MSFT"}
            assert mock_fetch.call_count == 3

    def test_rs_strength_calculated_when_ref_available(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """When ref symbol is requested, rs_strength should be calculated correctly.

        This validates that the fix doesn't break the rs_strength calculation
        when the reference symbol is available.
        """

        # Mock _fetch_daily to return predictable data
        def fetch_daily_mock(app: Any, symbol: str, days: int = 30) -> list:
            if symbol == "SPY":
                # SPY: 100 -> 110 = 10% return
                return [
                    ("20240101", 100.0, 100.0, 100.0, 100.0, 1000000),
                    *[("2024010" + str(i), 100.0, 100.0, 100.0, 100.0, 1000000) for i in range(2, 10)],
                    *[("202401" + str(i), 100.0, 100.0, 100.0, 100.0, 1000000) for i in range(10, 22)],
                    ("20240122", 110.0, 110.0, 110.0, 110.0, 1000000),
                ]
            elif symbol == "AAPL":
                # AAPL: 200 -> 240 = 20% return
                # rs_strength = 20% - 10% = 10% = 0.10
                return [
                    ("20240101", 200.0, 200.0, 200.0, 200.0, 2000000),
                    *[("2024010" + str(i), 200.0, 200.0, 200.0, 200.0, 2000000) for i in range(2, 10)],
                    *[("202401" + str(i), 200.0, 200.0, 200.0, 200.0, 2000000) for i in range(10, 22)],
                    ("20240122", 240.0, 240.0, 240.0, 240.0, 2000000),
                ]
            return []

        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", side_effect=fetch_daily_mock),
        ):
            result = fetcher.features_for_symbols(["AAPL", "SPY"])

            # Verify rs_strength is calculated for AAPL
            assert "rs_strength" in result["AAPL"]

            # Expected: AAPL 20% return - SPY 10% return = 10% = 0.10
            expected_rs = 0.10
            actual_rs = result["AAPL"]["rs_strength"]

            assert (
                abs(actual_rs - expected_rs) < 0.001
            ), f"rs_strength calculation incorrect: expected {expected_rs}, got {actual_rs}"

    def test_rs_strength_equals_absolute_return_when_ref_not_available(
        self, fetcher: RealTwsFetcher, mock_app: Mock
    ) -> None:
        """When ref symbol is NOT requested, rs_strength equals the symbol's absolute return.

        This validates that the fix handles the case where ref is not available
        by using ref_ret20=0.0, which makes rs_strength = sym_ret20 - 0.0 = sym_ret20.
        This is correct behavior: without a reference, relative strength becomes absolute return.
        """

        # Mock _fetch_daily to return predictable data
        def fetch_daily_mock(app: Any, symbol: str, days: int = 30) -> list:
            if symbol == "AAPL":
                # AAPL: 200 -> 240 = 20% return
                return [
                    ("20240101", 200.0, 200.0, 200.0, 200.0, 2000000),
                    *[("2024010" + str(i), 200.0, 200.0, 200.0, 200.0, 2000000) for i in range(2, 10)],
                    *[("202401" + str(i), 200.0, 200.0, 200.0, 200.0, 2000000) for i in range(10, 22)],
                    ("20240122", 240.0, 240.0, 240.0, 240.0, 2000000),
                ]
            return []

        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", side_effect=fetch_daily_mock),
        ):
            # Request AAPL without SPY
            result = fetcher.features_for_symbols(["AAPL"])

            # Verify rs_strength exists and equals the symbol's absolute return
            assert "rs_strength" in result["AAPL"]

            # Expected: AAPL 20% return, ref_ret20 = 0.0 (no ref)
            # rs_strength = 0.20 - 0.0 = 0.20 (absolute return)
            expected_rs = 0.20
            actual_rs = result["AAPL"]["rs_strength"]

            assert abs(actual_rs - expected_rs) < 0.001, (
                f"When ref not available, rs_strength should equal absolute return. "
                f"Expected {expected_rs}, got {actual_rs}"
            )

    def test_duplicate_symbols_handled_correctly(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Duplicate symbols in request should be deduplicated.

        This validates that the fix preserves the existing deduplication logic.
        """
        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            # Request with duplicates
            result = fetcher.features_for_symbols(["AAPL", "MSFT", "AAPL", "MSFT"])

            # Verify results only contain unique symbols
            assert set(result.keys()) == {"AAPL", "MSFT"}

            # Verify each symbol was only fetched once
            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]
            assert fetched_symbols.count("AAPL") == 1
            assert fetched_symbols.count("MSFT") == 1
            assert mock_fetch.call_count == 2

    def test_ref_symbol_case_sensitivity(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Reference symbol matching should be case-sensitive.

        This validates that "SPY" is different from "spy" in symbol matching.
        """
        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            # Request lowercase "spy" (different from ref "SPY")
            result = fetcher.features_for_symbols(["spy", "AAPL"])

            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]

            # "SPY" (uppercase ref) should NOT be fetched because "spy" != "SPY"
            assert "SPY" not in fetched_symbols
            assert "spy" in fetched_symbols
            assert "AAPL" in fetched_symbols
            assert isinstance(result, dict)

    def test_empty_symbols_list(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Empty symbols list should not fetch anything, including ref symbol.

        This is an edge case that validates the fix handles empty input gracefully.
        """
        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            result = fetcher.features_for_symbols([])

            # No symbols requested, so no fetches should occur
            assert mock_fetch.call_count == 0
            assert result == {}

    def test_performance_improvement_metrics(self, fetcher: RealTwsFetcher, mock_app: Mock) -> None:
        """Validate that the fix reduces network calls in typical usage.

        This test demonstrates the performance improvement from the fix.
        """
        call_counts_without_ref = 0
        call_counts_with_ref = 0

        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            # Scenario 1: Request 10 symbols WITHOUT ref
            mock_fetch.reset_mock()
            symbols_without_ref = [f"SYM{i}" for i in range(10)]
            fetcher.features_for_symbols(symbols_without_ref)
            call_counts_without_ref = mock_fetch.call_count

            # Scenario 2: Request 10 symbols WITH ref
            mock_fetch.reset_mock()
            symbols_with_ref = ["SPY"] + [f"SYM{i}" for i in range(9)]
            fetcher.features_for_symbols(symbols_with_ref)
            call_counts_with_ref = mock_fetch.call_count

        # Both scenarios should make the same number of calls (10)
        # Before the fix, scenario 1 would make 11 calls (10 + SPY)
        assert call_counts_without_ref == 10, f"Expected 10 fetches without ref, got {call_counts_without_ref}"
        assert call_counts_with_ref == 10, f"Expected 10 fetches with ref, got {call_counts_with_ref}"

        # The key improvement: we save 1 network call per request when ref not needed
        # In a production system making 1000s of requests, this is significant savings


class TestBug4Integration:
    """Integration tests validating the fix in realistic scenarios."""

    @pytest.fixture
    def mock_config(self) -> TwsConfig:
        """Create a test configuration."""
        return TwsConfig(
            host="127.0.0.1",
            port=7496,
            client_id=999,
            ref_symbol="SPY",
            handshake_timeout=1.0,
            hist_timeout=5.0,
        )

    def test_watchlist_without_ref_symbol(self, mock_config: TwsConfig) -> None:
        """Realistic scenario: scanning a watchlist that doesn't include SPY.

        This simulates a common use case where users scan sector-specific
        watchlists (e.g., biotech stocks) that don't include the market reference.
        """
        fetcher = RealTwsFetcher(cfg=mock_config)

        # Biotech watchlist (no SPY)
        biotech_watchlist = ["MRNA", "BNTX", "NVAX", "GILD", "REGN"]

        mock_app = Mock(spec=_HistApp)
        mock_app.errors = []
        mock_app.ready = threading.Event()
        mock_app.ready.set()
        mock_app.cleanup = Mock()

        def register_request_mock(req_id: int) -> threading.Event:
            evt = threading.Event()
            evt.set()
            return evt

        mock_app.register_request = Mock(side_effect=register_request_mock)
        mock_app.take_bars = Mock(
            return_value=[
                ("20240101", 100.0, 105.0, 99.0, 104.0, 1000000),
            ]
        )
        mock_app.release = Mock()
        mock_app.reqHistoricalData = Mock()

        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            result = fetcher.features_for_symbols(biotech_watchlist)

            # Verify all biotech symbols were fetched
            assert set(result.keys()) == set(biotech_watchlist)

            # Verify SPY was NOT fetched (saving 1 network call)
            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]
            assert "SPY" not in fetched_symbols

            # Verify exactly 5 fetches (not 6 with SPY)
            assert mock_fetch.call_count == len(biotech_watchlist)

    def test_mixed_watchlist_with_ref_symbol(self, mock_config: TwsConfig) -> None:
        """Realistic scenario: scanning a watchlist that includes SPY.

        This simulates a use case where the reference symbol is part of the
        watchlist (e.g., comparing individual stocks to the market index).
        """
        fetcher = RealTwsFetcher(cfg=mock_config)

        # Mixed watchlist including SPY
        mixed_watchlist = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN"]

        mock_app = Mock(spec=_HistApp)
        mock_app.errors = []
        mock_app.ready = threading.Event()
        mock_app.ready.set()
        mock_app.cleanup = Mock()

        def register_request_mock(req_id: int) -> threading.Event:
            evt = threading.Event()
            evt.set()
            return evt

        mock_app.register_request = Mock(side_effect=register_request_mock)
        mock_app.take_bars = Mock(
            return_value=[
                ("20240101", 100.0, 105.0, 99.0, 104.0, 1000000),
            ]
        )
        mock_app.release = Mock()
        mock_app.reqHistoricalData = Mock()

        with (
            patch.object(fetcher, "_connect", return_value=mock_app),
            patch.object(fetcher, "_fetch_daily", wraps=fetcher._fetch_daily) as mock_fetch,
        ):
            result = fetcher.features_for_symbols(mixed_watchlist)

            # Verify all symbols were fetched
            assert set(result.keys()) == set(mixed_watchlist)

            # Verify SPY was fetched FIRST
            fetched_symbols = [call[0][1] for call in mock_fetch.call_args_list]
            assert fetched_symbols[0] == "SPY"

            # Verify exactly 5 fetches (same as watchlist size)
            assert mock_fetch.call_count == len(mixed_watchlist)
