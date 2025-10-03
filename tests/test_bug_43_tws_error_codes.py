#!/usr/bin/env python3
"""Unit tests for Bug #43: Complete TWS error code coverage.

This test module verifies that the TWS error handler properly classifies
all known IB API error codes and handles them appropriately.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optipanel.adapters.ibkr.tws_fetcher import _BaseApp


class TestTWSErrorClassification:
    """Test suite for TWS error classification (Bug #43)."""

    def test_error_classifications_comprehensive(self):
        """Test that all major error code categories are covered."""
        app = _BaseApp()

        # Check that we have comprehensive coverage
        classifications = app._ERROR_CLASSIFICATIONS

        # Verify we have informational codes (1xxx)
        info_codes = [k for k, v in classifications.items() if v == "info" and 1000 <= k < 2000]
        assert len(info_codes) > 0, "Missing informational codes (1xxx)"

        # Verify we have warning codes (2xxx)
        warning_codes = [k for k, v in classifications.items() if v == "warning" and 2000 <= k < 3000]
        assert len(warning_codes) >= 10, "Insufficient warning codes (2xxx)"

        # Verify we have error codes (200-399)
        error_codes = [k for k, v in classifications.items() if v == "error" and 200 <= k < 400]
        assert len(error_codes) >= 10, "Insufficient error codes (200-399)"

        # Verify we have critical codes (500-599)
        critical_codes = [k for k, v in classifications.items() if v == "critical" and 500 <= k < 600]
        assert len(critical_codes) >= 10, "Insufficient critical codes (500-599)"

    def test_backward_compatibility_non_fatal(self):
        """Test that _NON_FATAL maintains backward compatibility."""
        app = _BaseApp()

        # Original non-fatal codes should still be present
        assert 2104 in app._NON_FATAL, "Missing original non-fatal code 2104"
        assert 2106 in app._NON_FATAL, "Missing original non-fatal code 2106"
        assert 2158 in app._NON_FATAL, "Missing original non-fatal code 2158"

        # Additional non-fatal codes should be included
        assert 2103 in app._NON_FATAL, "Missing non-fatal code 2103"
        assert 2105 in app._NON_FATAL, "Missing non-fatal code 2105"
        assert 2107 in app._NON_FATAL, "Missing non-fatal code 2107"

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_info_level(self, mock_logger, mock_record):
        """Test that info-level errors are logged correctly and not stored."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Test info-level error
        app.error(
            reqId=-1, errorTime=0, errorCode=1102, errorString="Connectivity restored", advancedOrderRejectJson=""
        )

        # Should log as info
        logger.info.assert_called_once()
        assert "TWS Error [INFO]" in logger.info.call_args[0][0]

        # Should not be added to errors list
        assert len(app.errors) == 0

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_warning_level(self, mock_logger, mock_record):
        """Test that warning-level errors are logged correctly and not stored."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Test warning-level error
        app.error(
            reqId=-1,
            errorTime=0,
            errorCode=2104,
            errorString="Market data farm connection is OK",
            advancedOrderRejectJson="",
        )

        # Should log as warning
        logger.warning.assert_called_once()
        assert "TWS Error [WARNING]" in logger.warning.call_args[0][0]

        # Should not be added to errors list
        assert len(app.errors) == 0

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_error_level(self, mock_logger, mock_record):
        """Test that error-level errors are logged and stored."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Test error-level error
        app.error(
            reqId=1, errorTime=0, errorCode=200, errorString="No security definition found", advancedOrderRejectJson=""
        )

        # Should log as error
        logger.error.assert_called_once()
        assert "TWS Error [ERROR]" in logger.error.call_args[0][0]

        # Should be added to errors list
        assert len(app.errors) == 1
        assert app.errors[0] == (200, "No security definition found")

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_critical_level(self, mock_logger, mock_record):
        """Test that critical-level errors are logged and stored."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Test critical-level error
        app.error(reqId=-1, errorTime=0, errorCode=504, errorString="Not connected to TWS", advancedOrderRejectJson="")

        # Should log as critical
        logger.critical.assert_called_once()
        assert "TWS Error [CRITICAL]" in logger.critical.call_args[0][0]

        # Should be added to errors list
        assert len(app.errors) == 1
        assert app.errors[0] == (504, "Not connected to TWS")

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_unknown_code(self, mock_logger, mock_record):
        """Test that unknown error codes default to 'error' level."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Test unknown error code
        app.error(reqId=-1, errorTime=0, errorCode=99999, errorString="Unknown error", advancedOrderRejectJson="")

        # Should log as error (default)
        logger.error.assert_called_once()
        assert "TWS Error [ERROR]" in logger.error.call_args[0][0]

        # Should be added to errors list
        assert len(app.errors) == 1
        assert app.errors[0] == (99999, "Unknown error")

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_error_handler_with_advanced_rejection(self, mock_logger, mock_record):
        """Test handling of advanced order rejection JSON."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        rejection_json = '{"reason": "insufficient margin", "details": {...}}'

        # Test error with advanced rejection JSON
        app.error(
            reqId=1, errorTime=0, errorCode=201, errorString="Order rejected", advancedOrderRejectJson=rejection_json
        )

        # Should log the main error
        assert logger.error.call_count == 2
        first_call = logger.error.call_args_list[0][0][0]
        assert "TWS Error [ERROR]" in first_call

        # Should also log the rejection details
        second_call = logger.error.call_args_list[1][0][0]
        assert "Order rejection details:" in second_call
        assert rejection_json in second_call

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    def test_metrics_recording(self, mock_record):
        """Test that metrics are recorded correctly."""
        app = _BaseApp()

        # Test various error levels
        app.error(reqId=-1, errorTime=0, errorCode=1102, errorString="Test", advancedOrderRejectJson="")
        app.error(reqId=-1, errorTime=0, errorCode=2104, errorString="Test", advancedOrderRejectJson="")
        app.error(reqId=-1, errorTime=0, errorCode=200, errorString="Test", advancedOrderRejectJson="")
        app.error(reqId=-1, errorTime=0, errorCode=504, errorString="Test", advancedOrderRejectJson="")

        # Should record both specific error codes and levels
        expected_calls = [
            "ibkr.error.1102",
            "ibkr.error_level.info",
            "ibkr.error.2104",
            "ibkr.error_level.warning",
            "ibkr.error.200",
            "ibkr.error_level.error",
            "ibkr.error.504",
            "ibkr.error_level.critical",
        ]

        actual_calls = [call[0][0] for call in mock_record.call_args_list]
        for expected in expected_calls:
            assert expected in actual_calls, f"Missing metric: {expected}"

    def test_error_accumulation_bounded(self):
        """Test that error accumulation is bounded (Bug #1 fix still works)."""
        app = _BaseApp()

        # Fill errors beyond max
        for i in range(app._MAX_ERRORS + 50):
            app.error(reqId=i, errorTime=0, errorCode=200, errorString=f"Error {i}", advancedOrderRejectJson="")

        # Should be bounded to MAX_ERRORS
        assert len(app.errors) == app._MAX_ERRORS

        # Should have the most recent errors
        last_error = app.errors[-1]
        assert last_error[1].startswith("Error")

    def test_all_critical_codes_classified(self):
        """Test that all known critical TWS errors are classified."""
        app = _BaseApp()

        # Known critical error codes from IB API
        critical_codes = [501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517]

        for code in critical_codes:
            assert code in app._ERROR_CLASSIFICATIONS, f"Missing critical code {code}"
            assert app._ERROR_CLASSIFICATIONS[code] == "critical", f"Code {code} should be critical"

    def test_market_data_farm_codes_non_fatal(self):
        """Test that market data farm connection codes are non-fatal."""
        app = _BaseApp()

        # Market data farm codes that should be non-fatal
        farm_codes = [2103, 2104, 2105, 2106, 2107, 2108, 2109, 2110, 2119, 2158]

        for code in farm_codes:
            assert code in app._NON_FATAL, f"Market data farm code {code} should be non-fatal"


class TestIntegrationScenarios:
    """Integration tests for real-world error scenarios."""

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_connection_recovery_sequence(self, mock_logger, mock_record):
        """Test handling of typical connection recovery sequence."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Simulate connection loss and recovery
        error_sequence = [
            (1100, "Connectivity between IB and TWS has been lost"),
            (2110, "Connectivity between TWS and server is broken"),
            (2119, "Market data farm is connecting"),
            (1101, "Connectivity between IB and TWS has been restored - data lost"),
            (2103, "Market data farm connection is OK"),
            (2104, "Market data farm connection is OK"),
        ]

        for code, msg in error_sequence:
            app.error(reqId=-1, errorTime=0, errorCode=code, errorString=msg, advancedOrderRejectJson="")

        # No errors should be stored (all are info/warning)
        assert len(app.errors) == 0

        # Should have appropriate logging
        assert logger.info.call_count >= 2
        assert logger.warning.call_count >= 4

    @patch("optipanel.adapters.ibkr.tws_fetcher.record")
    @patch("optipanel.adapters.ibkr.tws_fetcher.logging.getLogger")
    def test_order_rejection_flow(self, mock_logger, mock_record):
        """Test handling of order rejection with details."""
        logger = MagicMock()
        mock_logger.return_value = logger

        app = _BaseApp()

        # Simulate order rejection
        app.error(
            reqId=123,
            errorTime=1234567890,
            errorCode=201,
            errorString="Order rejected - insufficient margin",
            advancedOrderRejectJson='{"margin_required": 10000, "margin_available": 5000}',
        )

        # Error should be stored
        assert len(app.errors) == 1
        assert app.errors[0] == (201, "Order rejected - insufficient margin")

        # Both main error and details should be logged
        assert logger.error.call_count == 2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
