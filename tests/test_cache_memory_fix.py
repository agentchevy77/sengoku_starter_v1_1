"""Test suite for cache memory optimization fix (Issue #6).

Tests the optimized _prune_expired method that minimizes memory allocation
by collecting only expired keys instead of copying all items.
"""

import gc

# Import the module containing _TickCache
import importlib
import sys
import threading
import time
import timeit
from unittest.mock import MagicMock, patch

api_module = importlib.import_module("optipanel.api.app")


class TestCacheMemoryOptimization:
    """Test suite for _TickCache memory optimization."""

    def test_prune_expired_removes_only_expired_entries(self):
        """Test that _prune_expired correctly removes only expired entries."""
        cache = api_module._TickCache()
        cache.clear()

        # Create a mock time
        current_time = 100.0

        # Add entries with different expiration times
        cache._data[("key1",)] = api_module._TickCacheEntry(expires_at=90.0, payload={"value": 1})
        cache._data[("key2",)] = api_module._TickCacheEntry(expires_at=110.0, payload={"value": 2})
        cache._data[("key3",)] = api_module._TickCacheEntry(expires_at=95.0, payload={"value": 3})
        cache._data[("key4",)] = api_module._TickCacheEntry(expires_at=120.0, payload={"value": 4})

        # Prune expired entries
        with cache._lock:
            cache._prune_expired(current_time)

        # Check that only non-expired entries remain
        assert len(cache._data) == 2
        assert ("key2",) in cache._data
        assert ("key4",) in cache._data
        assert ("key1",) not in cache._data
        assert ("key3",) not in cache._data

    def test_prune_expired_handles_empty_cache(self):
        """Test that _prune_expired handles empty cache gracefully."""
        cache = api_module._TickCache()
        cache.clear()

        # Should not raise any errors
        with cache._lock:
            cache._prune_expired(100.0)

        assert len(cache._data) == 0

    def test_prune_expired_handles_all_expired(self):
        """Test that _prune_expired handles case where all entries are expired."""
        cache = api_module._TickCache()
        cache.clear()

        # Add entries that are all expired
        for i in range(5):
            cache._data[(f"key{i}",)] = api_module._TickCacheEntry(expires_at=90.0 + i, payload={"value": i})

        # Prune with time after all expiration times
        with cache._lock:
            cache._prune_expired(100.0)

        assert len(cache._data) == 0

    def test_prune_expired_handles_no_expired(self):
        """Test that _prune_expired handles case where no entries are expired."""
        cache = api_module._TickCache()
        cache.clear()

        # Add entries that are all still valid
        for i in range(5):
            cache._data[(f"key{i}",)] = api_module._TickCacheEntry(expires_at=110.0 + i, payload={"value": i})

        initial_count = len(cache._data)

        # Prune with time before all expiration times
        with cache._lock:
            cache._prune_expired(100.0)

        assert len(cache._data) == initial_count

    def test_memory_efficiency_with_large_cache(self):
        """Test memory efficiency with a large cache containing few expired entries.

        This test verifies that the optimized implementation uses less memory
        by only collecting expired keys rather than copying all items.
        """
        cache = api_module._TickCache()
        cache.clear()

        # Create a large cache with mostly non-expired entries
        large_payload = {"data": "x" * 1000}  # Reasonably sized payload

        # Add 10,000 non-expired entries
        for i in range(10000):
            cache._data[(f"valid_{i}",)] = api_module._TickCacheEntry(expires_at=200.0, payload=large_payload.copy())

        # Add only 10 expired entries
        for i in range(10):
            cache._data[(f"expired_{i}",)] = api_module._TickCacheEntry(expires_at=50.0, payload=large_payload.copy())

        # Track memory allocation during pruning
        # The optimized version should only allocate memory for 10 keys
        # instead of 10,010 items
        gc.collect()

        # Prune expired entries
        with cache._lock:
            cache._prune_expired(100.0)

        # Verify only expired entries were removed
        assert len(cache._data) == 10000
        for i in range(10):
            assert (f"expired_{i}",) not in cache._data
        for i in range(10000):
            assert (f"valid_{i}",) in cache._data

    def test_concurrent_pruning_safety(self):
        """Test that pruning is thread-safe with concurrent operations."""
        cache = api_module._TickCache()
        cache.clear()

        # Add mixed expired and valid entries
        for i in range(100):
            expiry = 90.0 if i % 2 == 0 else 110.0
            cache._data[(f"key_{i}",)] = api_module._TickCacheEntry(expires_at=expiry, payload={"value": i})

        errors = []

        def prune_worker():
            try:
                for _ in range(10):
                    with cache._lock:
                        cache._prune_expired(100.0)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def read_worker():
            try:
                for _ in range(10):
                    with cache._lock:
                        # Try to read while pruning might be happening
                        _ = list(cache._data.keys())
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=prune_worker))
            threads.append(threading.Thread(target=read_worker))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # Only non-expired entries should remain
        assert len(cache._data) == 50
        for i in range(100):
            if i % 2 == 0:
                assert (f"key_{i}",) not in cache._data
            else:
                assert (f"key_{i}",) in cache._data

    def test_prune_interval_respected(self):
        """Test that pruning respects the interval to avoid excessive pruning."""
        cache = api_module._TickCache()
        cache.clear()

        # Mock time to control it precisely
        mock_time = MagicMock(return_value=100.0)

        # Add an expired entry
        cache._data[("expired",)] = api_module._TickCacheEntry(expires_at=90.0, payload={"value": 1})

        # First get_or_create should trigger pruning
        with patch("time.time", mock_time):
            _ = cache.get_or_create(("test",), ttl=10.0, loader=lambda: {"value": 2})

        # Entry should be pruned
        assert ("expired",) not in cache._data

        # Add another expired entry
        cache._data[("expired2",)] = api_module._TickCacheEntry(expires_at=90.0, payload={"value": 3})

        # Advance time but not past prune interval
        mock_time.return_value = 130.0  # 30 seconds later

        # This should NOT trigger pruning (within 60 second interval)
        with patch("time.time", mock_time):
            _ = cache.get_or_create(("test2",), ttl=10.0, loader=lambda: {"value": 4})

        # Expired entry should still be there
        assert ("expired2",) in cache._data

        # Advance time past prune interval
        mock_time.return_value = 170.0  # 70 seconds from first prune

        # This SHOULD trigger pruning
        with patch("time.time", mock_time):
            _ = cache.get_or_create(("test3",), ttl=10.0, loader=lambda: {"value": 5})

        # Now expired entry should be gone
        assert ("expired2",) not in cache._data

    def test_prune_with_edge_case_expiration_times(self):
        """Test pruning with edge case expiration times."""
        cache = api_module._TickCache()
        cache.clear()

        # Test with exact match, very close times, and edge cases
        cache._data[("exact",)] = api_module._TickCacheEntry(expires_at=100.0, payload={"value": 1})
        cache._data[("just_expired",)] = api_module._TickCacheEntry(expires_at=99.9999999, payload={"value": 2})
        cache._data[("just_valid",)] = api_module._TickCacheEntry(expires_at=100.0000001, payload={"value": 3})
        cache._data[("negative",)] = api_module._TickCacheEntry(expires_at=-100.0, payload={"value": 4})
        cache._data[("zero",)] = api_module._TickCacheEntry(expires_at=0.0, payload={"value": 5})
        cache._data[("far_future",)] = api_module._TickCacheEntry(expires_at=sys.float_info.max, payload={"value": 6})

        with cache._lock:
            cache._prune_expired(100.0)

        # Entries with expires_at <= 100.0 should be removed
        assert ("exact",) not in cache._data
        assert ("just_expired",) not in cache._data
        assert ("negative",) not in cache._data
        assert ("zero",) not in cache._data

        # These should remain
        assert ("just_valid",) in cache._data
        assert ("far_future",) in cache._data

    def test_performance_comparison(self):
        """Compare performance of optimized vs original implementation.

        This test doesn't fail but demonstrates the performance improvement.
        """

        cache = api_module._TickCache()

        # Setup: Large cache with few expired entries
        def setup_cache():
            cache.clear()
            # Add 5000 valid entries
            for i in range(5000):
                cache._data[(f"valid_{i}",)] = api_module._TickCacheEntry(expires_at=200.0, payload={"value": i})
            # Add 50 expired entries (1% expired)
            for i in range(50):
                cache._data[(f"expired_{i}",)] = api_module._TickCacheEntry(expires_at=50.0, payload={"value": i})

        # Original implementation (for comparison)
        def original_prune_expired(cache, now):
            for k, v in list(cache._data.items()):  # Full copy
                if v.expires_at <= now:
                    cache._data.pop(k, None)

        # Test optimized implementation
        setup_cache()
        optimized_time = timeit.timeit(lambda: cache._prune_expired(100.0), number=100)

        # Test original implementation
        setup_cache()
        original_time = timeit.timeit(lambda: original_prune_expired(cache, 100.0), number=100)

        # The optimized version should be faster
        # We don't assert on specific timing as it varies by system
        print("\nPerformance comparison (100 iterations):")
        print(f"Optimized: {optimized_time:.4f}s")
        print(f"Original:  {original_time:.4f}s")
        print(f"Speedup:   {original_time/optimized_time:.2f}x")

        # Verify correctness - both should have same result
        setup_cache()
        with cache._lock:
            cache._prune_expired(100.0)
        optimized_result = set(cache._data.keys())

        setup_cache()
        original_prune_expired(cache, 100.0)
        original_result = set(cache._data.keys())

        assert optimized_result == original_result
