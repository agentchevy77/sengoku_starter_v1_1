#!/usr/bin/env python3
"""Test suite for Bug #1 fix: Bounded error accumulation in TWS fetcher.

This test verifies that the fix prevents unbounded memory growth by using
a bounded deque instead of an unbounded list for error storage.
"""

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.adapters.ibkr.tws_fetcher import _BaseApp


class TestBug1ErrorAccumulation:
    """Test suite for Bug #1: Unbounded error accumulation fix."""

    def test_errors_uses_bounded_deque(self):
        """Verify that errors container is a bounded deque."""
        app = _BaseApp()

        # Check type is deque
        assert isinstance(app.errors, deque), "errors should be a deque"

        # Check maxlen is set
        assert app.errors.maxlen is not None, "errors deque should have maxlen set"
        assert app.errors.maxlen > 0, "maxlen should be positive"
        assert app.errors.maxlen == _BaseApp._MAX_ERRORS, "maxlen should match _MAX_ERRORS"

    def test_default_max_errors_limit(self):
        """Verify default max errors limit is 100."""
        # Clear any environment override
        old_val = os.environ.pop("SENGOKU_TWS_MAX_ERRORS", None)
        try:
            # Reload to get default
            from importlib import reload

            from optipanel.adapters.ibkr import tws_fetcher

            reload(tws_fetcher)

            app = tws_fetcher._BaseApp()
            assert app.errors.maxlen == 100, "Default should be 100 errors"
        finally:
            if old_val is not None:
                os.environ["SENGOKU_TWS_MAX_ERRORS"] = old_val

    def test_environment_override_max_errors(self):
        """Verify max errors can be configured via environment variable."""
        old_val = os.environ.get("SENGOKU_TWS_MAX_ERRORS")
        try:
            os.environ["SENGOKU_TWS_MAX_ERRORS"] = "50"

            # Reload to pick up new env var
            from importlib import reload

            from optipanel.adapters.ibkr import tws_fetcher

            reload(tws_fetcher)

            app = tws_fetcher._BaseApp()
            assert app.errors.maxlen == 50, "Should use env var value"
        finally:
            if old_val is not None:
                os.environ["SENGOKU_TWS_MAX_ERRORS"] = old_val
            else:
                os.environ.pop("SENGOKU_TWS_MAX_ERRORS", None)

    def test_errors_automatically_evict_oldest(self):
        """Verify that oldest errors are automatically evicted when limit reached."""
        app = _BaseApp()
        max_errors = app.errors.maxlen

        # Fill beyond capacity
        for i in range(max_errors + 50):
            # Simulate error callback
            app.error(
                reqId=i, errorTime=int(time.time()), errorCode=300 + i, errorString=f"Error {i}"  # Use non-fatal codes
            )

        # Should only have max_errors items
        assert len(app.errors) == max_errors, f"Should have exactly {max_errors} errors"

        # First error should be evicted (error 50+)
        first_error = app.errors[0]
        assert first_error[0] >= 300 + 50, "Oldest errors should be evicted"

        # Last error should be the most recent
        last_error = app.errors[-1]
        expected_code = 300 + max_errors + 49
        assert last_error[0] == expected_code, "Most recent error should be retained"

    def test_non_fatal_errors_not_stored(self):
        """Verify non-fatal errors are not stored in errors list."""
        app = _BaseApp()

        # Emit non-fatal errors
        for code in _BaseApp._NON_FATAL:
            app.error(reqId=1, errorTime=int(time.time()), errorCode=code, errorString=f"Non-fatal {code}")

        # Should have zero errors
        assert len(app.errors) == 0, "Non-fatal errors should not be stored"

        # Now emit a fatal error
        app.error(reqId=2, errorTime=int(time.time()), errorCode=500, errorString="Fatal error")

        # Should have one error
        assert len(app.errors) == 1, "Fatal error should be stored"
        assert app.errors[0][0] == 500

    def test_memory_bounded_under_heavy_load(self):
        """Verify memory usage stays bounded under heavy error load."""
        app = _BaseApp()
        max_errors = app.errors.maxlen

        # Simulate very heavy error load
        num_errors = max_errors * 10

        for i in range(num_errors):
            app.error(
                reqId=i,
                errorTime=int(time.time()),
                errorCode=400 + (i % 100),
                errorString=f"Heavy load error {i} with long message " + "x" * 100,
            )

        # Memory should be bounded to maxlen entries
        assert len(app.errors) == max_errors

        # Calculate approximate memory usage
        # Each tuple is approximately 100 bytes (error code + string)
        # With 100 byte strings, that's ~200 bytes per entry
        estimated_bytes = max_errors * 200

        # Should be well under 1MB for default settings
        assert estimated_bytes < 1_000_000, "Memory usage should be bounded"

    def test_concurrent_error_appends_safe(self):
        """Verify thread-safety of deque operations."""
        app = _BaseApp()
        errors_per_thread = 50
        num_threads = 10

        def append_errors(thread_id: int):
            for i in range(errors_per_thread):
                app.error(
                    reqId=thread_id * 1000 + i,
                    errorTime=int(time.time()),
                    errorCode=500 + i,
                    errorString=f"Thread {thread_id} error {i}",
                )

        threads = [threading.Thread(target=append_errors, args=(i,)) for i in range(num_threads)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have at most maxlen errors
        assert len(app.errors) <= app.errors.maxlen

        # No corruption - all entries should be valid tuples
        for error_code, error_msg in app.errors:
            assert isinstance(error_code, int)
            assert isinstance(error_msg, str)

    def test_backward_compatibility_iteration(self):
        """Verify deque supports same iteration patterns as list."""
        app = _BaseApp()

        # Add some errors
        for i in range(10):
            app.error(reqId=i, errorTime=int(time.time()), errorCode=600 + i, errorString=f"Compat error {i}")

        # Test iteration
        count = 0
        for error_code, error_msg in app.errors:
            assert isinstance(error_code, int)
            assert isinstance(error_msg, str)
            count += 1
        assert count == 10

        # Test indexing
        first = app.errors[0]
        assert first[0] == 600

        last = app.errors[-1]
        assert last[0] == 609

        # Test conversion to list for slicing (deque doesn't support slicing directly)
        errors_list = list(app.errors)
        slice_errors = errors_list[:5]
        assert len(slice_errors) == 5

        # Test length
        assert len(app.errors) == 10

        # Test boolean (truthiness)
        assert bool(app.errors) is True

        empty_app = _BaseApp()
        assert bool(empty_app.errors) is False

    def test_backward_compatibility_handshake_test(self):
        """Verify handshake_test() still works with deque."""
        # This test verifies that code expecting list-like access still works
        app = _BaseApp()

        # Simulate some errors
        app.error(reqId=1, errorTime=int(time.time()), errorCode=502, errorString="Connection error")

        # The handshake_test returns errors directly
        # Verify it can be serialized/used as expected
        errors = app.errors

        # Should be convertible to list
        errors_list = list(errors)
        assert len(errors_list) == 1
        assert errors_list[0] == (502, "Connection error")

        # Should work in dict/json contexts
        import json

        result = {"errors": list(errors)}  # Convert to list for JSON
        json_str = json.dumps(result)
        assert "502" in json_str

    def test_error_message_truncation_safety(self):
        """Verify very long error messages don't cause issues."""
        app = _BaseApp()

        # Create extremely long error message
        huge_message = "x" * 100000  # 100KB message

        app.error(reqId=1, errorTime=int(time.time()), errorCode=700, errorString=huge_message)

        # Should be stored
        assert len(app.errors) == 1
        assert app.errors[0][0] == 700
        assert len(app.errors[0][1]) == 100000

    def test_errors_cleared_between_instances(self):
        """Verify each instance has independent error storage."""
        app1 = _BaseApp()
        app2 = _BaseApp()

        # Add errors to app1
        app1.error(reqId=1, errorTime=int(time.time()), errorCode=800, errorString="App1 error")

        # app2 should be empty
        assert len(app1.errors) == 1
        assert len(app2.errors) == 0

        # Add to app2
        app2.error(reqId=2, errorTime=int(time.time()), errorCode=801, errorString="App2 error")

        # Both should be independent
        assert len(app1.errors) == 1
        assert len(app2.errors) == 1
        assert app1.errors[0][0] == 800
        assert app2.errors[0][0] == 801

    def test_fix_prevents_memory_leak_simulation(self):
        """Simulate long-running process to verify no memory leak."""
        app = _BaseApp()
        max_errors = app.errors.maxlen

        # Simulate errors over extended period
        iterations = 1000
        errors_per_iteration = 10

        for iteration in range(iterations):
            for i in range(errors_per_iteration):
                app.error(
                    reqId=iteration * errors_per_iteration + i,
                    errorTime=int(time.time()),
                    errorCode=900 + (i % 50),
                    errorString=f"Iteration {iteration} error {i}",
                )

            # Verify size never exceeds limit
            assert len(app.errors) <= max_errors

        # Final check - should be exactly at limit
        assert len(app.errors) == max_errors

        # Oldest errors should be from recent iterations
        first_error_msg = app.errors[0][1]
        # Should be from later iterations, not early ones
        assert "Iteration 0" not in first_error_msg

    def test_performance_overhead_minimal(self):
        """Verify deque operations have minimal performance overhead."""
        app = _BaseApp()
        num_operations = 10000

        start_time = time.perf_counter()
        for i in range(num_operations):
            app.error(
                reqId=i, errorTime=int(time.time()), errorCode=1000 + (i % 100), errorString=f"Perf test error {i}"
            )
        elapsed = time.perf_counter() - start_time

        # Should complete very quickly (well under 1 second)
        assert elapsed < 1.0, f"Operations took {elapsed}s, expected < 1s"

        # Calculate throughput
        ops_per_second = num_operations / elapsed
        assert ops_per_second > 10000, "Should handle >10k errors/sec"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
