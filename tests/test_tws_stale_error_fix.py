"""
Comprehensive tests for Issue #2: Stale Error State Fix in TWS Fetcher

This test suite validates that the error state (_last_error) is properly
updated on ALL exception types, not just TimeoutError, preventing stale
error messages from misleading diagnostics.
"""

from unittest.mock import MagicMock, patch

import pytest

from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig


class TestStaleErrorStateFix:
    """Test suite for the stale error state fix in RealTwsFetcher._connect"""

    @pytest.fixture
    def config(self):
        """Create a test configuration"""
        return TwsConfig(
            host="127.0.0.1",
            port=7497,
            client_id=999,
            handshake_timeout=1.0,
        )

    @pytest.fixture
    def fetcher(self, config):
        """Create a fetcher instance with test config"""
        return RealTwsFetcher(cfg=config)

    def test_timeout_error_sets_last_error(self, fetcher):
        """Test that TimeoutError properly sets _last_error"""
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            # Setup mock to simulate timeout
            mock_app = mock_app_cls.return_value
            mock_app.connect = MagicMock()
            mock_app.ready = MagicMock()
            mock_app.ready.wait = MagicMock(return_value=False)  # Timeout
            mock_app.disconnect = MagicMock()

            # Attempt connection
            with pytest.raises(TimeoutError):
                fetcher._connect()

            # Verify _last_error is set correctly for timeout
            assert fetcher._last_error is not None
            assert "handshake timeout" in fetcher._last_error
            assert "127.0.0.1" in fetcher._last_error
            assert "7497" in fetcher._last_error
            assert "999" in fetcher._last_error

    def test_connection_refused_sets_last_error(self, fetcher):
        """Test that ConnectionRefusedError properly sets _last_error"""
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            # Setup mock to raise ConnectionRefusedError
            mock_app = mock_app_cls.return_value
            mock_app.connect = MagicMock(side_effect=ConnectionRefusedError("Connection refused"))
            mock_app.disconnect = MagicMock()

            # Clear any previous error to ensure test validity
            fetcher._last_error = None

            # Attempt connection
            with pytest.raises(ConnectionRefusedError):
                fetcher._connect()

            # CRITICAL VALIDATION: _last_error must be updated with current error
            assert fetcher._last_error is not None
            assert "ConnectionRefusedError" in fetcher._last_error
            assert "Connection refused" in fetcher._last_error
            assert "127.0.0.1" in fetcher._last_error
            assert "7497" in fetcher._last_error

    def test_generic_exception_sets_last_error(self, fetcher):
        """Test that generic exceptions properly set _last_error"""
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            # Setup mock to raise a generic exception
            mock_app = mock_app_cls.return_value
            mock_app.connect = MagicMock(side_effect=RuntimeError("Unexpected error occurred"))
            mock_app.disconnect = MagicMock()

            # Clear any previous error
            fetcher._last_error = None

            # Attempt connection
            with pytest.raises(RuntimeError):
                fetcher._connect()

            # Verify _last_error is updated with the generic exception
            assert fetcher._last_error is not None
            assert "RuntimeError" in fetcher._last_error
            assert "Unexpected error occurred" in fetcher._last_error
            assert fetcher.cfg.host in fetcher._last_error

    def test_stale_error_not_retained_after_non_timeout_failure(self, fetcher):
        """
        CRITICAL TEST: Validates the fix for Issue #2

        This test simulates the exact bug scenario:
        1. First connection fails with TimeoutError
        2. Second connection fails with different error (e.g., ConnectionError)
        3. Verify that _last_error reflects the SECOND error, not the first
        """
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            mock_app = mock_app_cls.return_value
            mock_app.disconnect = MagicMock()

            # Step 1: First attempt - TimeoutError
            mock_app.connect = MagicMock()
            mock_app.ready = MagicMock()
            mock_app.ready.wait = MagicMock(return_value=False)  # Timeout

            with pytest.raises(TimeoutError):
                fetcher._connect()

            first_error = fetcher._last_error
            assert first_error is not None
            assert "handshake timeout" in first_error

            # Step 2: Second attempt - Different error type
            mock_app.connect = MagicMock(side_effect=ConnectionError("Network unreachable"))

            with pytest.raises(ConnectionError):
                fetcher._connect()

            second_error = fetcher._last_error

            # CRITICAL ASSERTION: The error must be from the SECOND attempt
            assert second_error is not None
            assert second_error != first_error  # Must be different!
            assert "ConnectionError" in second_error
            assert "Network unreachable" in second_error
            assert "handshake timeout" not in second_error  # No stale timeout message

    def test_successful_connection_clears_last_error(self, fetcher):
        """Test that successful connection clears _last_error"""
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            # Setup for failed attempt first
            mock_app = mock_app_cls.return_value
            mock_app.connect = MagicMock(side_effect=ConnectionError("Initial failure"))
            mock_app.disconnect = MagicMock()

            with pytest.raises(ConnectionError):
                fetcher._connect()

            assert fetcher._last_error is not None  # Error is set

            # Now setup for successful connection
            mock_app.connect = MagicMock()  # No exception
            mock_app.ready = MagicMock()
            mock_app.ready.wait = MagicMock(return_value=True)  # Success
            mock_app.run = MagicMock()

            with patch("threading.Thread") as mock_thread_cls:
                mock_thread = mock_thread_cls.return_value
                mock_thread.start = MagicMock()
                mock_thread.is_alive = MagicMock(return_value=True)

                fetcher._connect()

                # Verify error is cleared on success
                assert fetcher._last_error is None
                assert fetcher._last_ok > 0

    def test_error_message_includes_connection_details(self, fetcher):
        """Test that error messages include host, port, and client_id for debugging"""
        test_errors = [
            ConnectionRefusedError("refused"),
            OSError("socket error"),
            ValueError("invalid parameter"),
            RuntimeError("runtime issue"),
        ]

        for error in test_errors:
            with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
                mock_app = mock_app_cls.return_value
                mock_app.connect = MagicMock(side_effect=error)
                mock_app.disconnect = MagicMock()

                fetcher._last_error = None  # Clear before test

                with pytest.raises(type(error)):
                    fetcher._connect()

                # Each error should include connection details
                assert fetcher._last_error is not None
                assert str(fetcher.cfg.host) in fetcher._last_error
                assert str(fetcher.cfg.port) in fetcher._last_error
                assert str(fetcher.cfg.client_id) in fetcher._last_error
                assert type(error).__name__ in fetcher._last_error

    def test_last_error_message_method_returns_current_state(self, fetcher):
        """Test that last_error_message() returns the current error state"""
        # Initially None
        assert fetcher.last_error_message() is None

        # Set an error through failed connection
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            mock_app = mock_app_cls.return_value
            mock_app.connect = MagicMock(side_effect=OSError("Test IO error"))
            mock_app.disconnect = MagicMock()

            with pytest.raises(IOError):
                fetcher._connect()

        # Should return the error
        error_msg = fetcher.last_error_message()
        assert error_msg is not None
        # Note: In Python 3, IOError is aliased to OSError
        assert "IOError" in error_msg or "OSError" in error_msg
        assert "Test IO error" in error_msg

    def test_thread_cleanup_preserves_error_state(self, fetcher):
        """Test that thread cleanup operations don't affect error state tracking"""
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            mock_app = mock_app_cls.return_value
            mock_app.disconnect = MagicMock()

            # Simulate error that happens BEFORE thread creation (no thread to clean up)
            mock_app.connect = MagicMock(side_effect=RuntimeError("Early connection error"))

            with pytest.raises(RuntimeError):
                fetcher._connect()

            # Verify error is set even when no thread cleanup needed
            assert fetcher._last_error is not None
            assert "RuntimeError" in fetcher._last_error
            assert "Early connection error" in fetcher._last_error

        # Now test with thread cleanup scenario
        with patch("optipanel.adapters.ibkr.tws_fetcher._HistApp") as mock_app_cls:
            mock_app = mock_app_cls.return_value
            mock_app.disconnect = MagicMock()
            mock_app.connect = MagicMock()  # Success on connect
            mock_app.ready = MagicMock()
            mock_app.ready.wait = MagicMock(side_effect=RuntimeError("Error during wait"))

            with patch("threading.Thread") as mock_thread_cls:
                mock_thread = mock_thread_cls.return_value
                mock_thread.start = MagicMock()
                mock_thread.is_alive = MagicMock(return_value=True)
                mock_thread.join = MagicMock()

                with pytest.raises(RuntimeError):
                    fetcher._connect()

                # Verify error is set despite thread cleanup
                assert fetcher._last_error is not None
                assert "RuntimeError" in fetcher._last_error
                assert "Error during wait" in fetcher._last_error

                # Thread should have been cleaned up
                mock_thread.join.assert_called_once()


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
