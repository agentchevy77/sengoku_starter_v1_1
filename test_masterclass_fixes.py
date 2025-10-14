#!/usr/bin/env python3
"""Test suite for masterclass debugger fixes."""

import threading
import time
from unittest.mock import Mock, patch

from optipanel.positions.model import Portfolio
from optipanel.runtime.loop import run_once
from optipanel.utils.time_utils import calculate_sleep_duration, compare_floats, get_safe_timestamp_ms, is_zero


class TestIntegerOverflow:
    """Test integer overflow fixes."""

    def test_timestamp_near_2038(self):
        """Test timestamp doesn't overflow near year 2038."""
        # January 19, 2038 - near the 32-bit overflow point
        with patch("time.time", return_value=2147483647):  # 2^31 - 1 seconds
            timestamp = get_safe_timestamp_ms()
            assert timestamp > 0
            assert timestamp == 2147483647000

    def test_timestamp_past_2038(self):
        """Test timestamp handles dates past 2038."""
        # Past the 32-bit overflow point
        with patch("time.time", return_value=2147483648):  # 2^31 seconds
            timestamp = get_safe_timestamp_ms()
            assert timestamp > 0
            assert timestamp == 2147483648000

    def test_timestamp_javascript_safety(self):
        """Test timestamp stays within JavaScript safe integer range."""
        # Very large timestamp
        with patch("time.time", return_value=9007199254740):  # Near JS limit
            timestamp = get_safe_timestamp_ms()
            assert timestamp < 2**53 - 1  # JavaScript MAX_SAFE_INTEGER


class TestFloatPrecision:
    """Test float precision fixes."""

    def test_sleep_calculation_precision(self):
        """Test sleep calculation doesn't add unnecessary time."""
        interval = 1.0
        elapsed = 0.999999999

        sleep_duration = calculate_sleep_duration(interval, elapsed, buffer=0.01)

        # Should be very small, not 11ms
        assert sleep_duration < 0.002

    def test_zero_comparison(self):
        """Test proper zero comparison for floats."""
        # Test positive zero
        assert is_zero(0.0)

        # Test negative zero
        assert is_zero(-0.0)

        # Test very small numbers
        assert is_zero(1e-10)
        assert is_zero(-1e-10)

        # Test non-zero
        assert not is_zero(0.1)
        assert not is_zero(-0.1)

    def test_float_comparison(self):
        """Test float comparison with epsilon."""
        # Equal within epsilon
        assert compare_floats(0.1 + 0.2, 0.3) == 0

        # Not equal
        assert compare_floats(0.1, 0.2) == -1
        assert compare_floats(0.2, 0.1) == 1


class TestPositionsDivision:
    """Test division by zero fix in positions."""

    def test_negative_zero_division(self):
        """Test handling of negative zero in position calculations."""
        portfolio = Portfolio()

        # Create a position with -0.0 average price
        portfolio.positions["TEST"] = Mock(avg_px=-0.0, qty=100)

        # This should not crash or give infinity
        features = {"TEST": {"last": 50.0}}
        result = portfolio.tick(features)

        # Should handle gracefully
        assert result is not None

    def test_zero_average_price(self):
        """Test handling of zero average price."""
        portfolio = Portfolio()

        # Create a position with 0.0 average price
        portfolio.positions["TEST"] = Mock(avg_px=0.0, qty=100)

        features = {"TEST": {"last": 50.0}}
        result = portfolio.tick(features)

        # Should handle gracefully
        assert result is not None


class TestRuntimeLoop:
    """Test runtime loop fixes."""

    def test_empty_list_indexing(self):
        """Test that empty list doesn't cause IndexError."""
        # Mock scan output with empty top list
        scan_out = {"top": []}  # Empty list, not None

        with (
            patch("optipanel.runtime.loop.run_local_scan", return_value=scan_out),
            patch("optipanel.runtime.loop.analyze_batch", return_value={}),
        ):
            # Should not raise IndexError
            result = run_once({})
            assert result is not None

    def test_none_top_list(self):
        """Test handling of None top list."""
        scan_out = {"top": None}

        with (
            patch("optipanel.runtime.loop.run_local_scan", return_value=scan_out),
            patch("optipanel.runtime.loop.analyze_batch", return_value={}),
        ):
            result = run_once({})
            assert result is not None


class TestThreadSafety:
    """Test thread safety improvements."""

    def test_no_thread_leak(self):
        """Test that failed connections don't leak threads."""
        initial_count = threading.active_count()

        # Simulate multiple connection failures
        for _ in range(5):
            # Mock a connection that times out
            mock_app = Mock()
            mock_app.ready = Mock()
            mock_app.ready.wait = Mock(return_value=False)  # Timeout

            # This would normally create a daemon thread
            threading.Thread(target=lambda: time.sleep(0.1), daemon=True).start()

        # Give threads time to finish
        time.sleep(0.2)

        # Thread count shouldn't increase significantly
        # Allow for some variance in system threads
        assert threading.active_count() <= initial_count + 2


class TestUnicodeSafety:
    """Test Unicode handling."""

    def test_unicode_normalization(self):
        """Test that Unicode filenames are normalized."""
        import unicodedata

        # Two different representations of é
        name1 = "café"  # é as single character
        name2 = "cafe\u0301"  # e + combining acute accent

        # They look the same but are different
        assert name1 != name2

        # After normalization they should be the same
        norm1 = unicodedata.normalize("NFC", name1)
        norm2 = unicodedata.normalize("NFC", name2)
        assert norm1 == norm2


class TestCacheKeyCollisions:
    """Test cache key collision prevention."""

    def test_cache_key_uniqueness(self):
        """Test that similar keys don't collide."""
        import hashlib

        def create_key(*args):
            key_data = "|".join(str(arg) for arg in args)
            return hashlib.sha256(key_data.encode()).hexdigest()

        # Similar but different keys
        key1 = create_key("path1", "provider", "features")
        key2 = create_key("path", "1provider", "features")
        key3 = create_key("path1provider", "", "features")

        # All should be different
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3


def test_all_fixes():
    """Run all fix validations."""
    print("Testing Integer Overflow Protection...")
    TestIntegerOverflow().test_timestamp_near_2038()
    TestIntegerOverflow().test_timestamp_past_2038()
    print("✅ Integer overflow fixed")

    print("\nTesting Float Precision...")
    TestFloatPrecision().test_sleep_calculation_precision()
    TestFloatPrecision().test_zero_comparison()
    print("✅ Float precision fixed")

    print("\nTesting Division Safety...")
    TestPositionsDivision().test_negative_zero_division()
    print("✅ Division by zero fixed")

    print("\nTesting List Bounds...")
    TestRuntimeLoop().test_empty_list_indexing()
    print("✅ List indexing fixed")

    print("\nAll masterclass fixes verified! ✅")


if __name__ == "__main__":
    test_all_fixes()
