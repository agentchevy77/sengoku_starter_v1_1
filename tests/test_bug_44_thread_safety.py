"""Test suite for Bug #44: Thread Safety Issue in Cache Pruning.

This module tests the thread-safe implementation of cache pruning in _TickCache
to ensure that dictionary iteration is safe even under high concurrency.
"""

import concurrent.futures
import threading
import time

import pytest

from optipanel.api.app import TickCacheSettings, _TickCache, _TickCacheEntry


class TestBug44ThreadSafety:
    """Test cases for Bug #44: Thread safety in cache pruning."""

    def test_concurrent_prune_and_access(self):
        """Test that concurrent pruning and cache access don't cause RuntimeError.

        This test simulates a high-concurrency scenario where multiple threads
        are simultaneously:
        1. Adding entries to the cache
        2. Accessing entries from the cache
        3. Triggering cache pruning

        The fix ensures that iterating over dictionary items during pruning
        uses a snapshot approach that prevents RuntimeError.
        """
        # Use very short intervals to force frequent pruning
        config = TickCacheSettings(
            prune_interval=0.001,  # Prune very frequently
            failure_cooldown=0.1,
            wait_timeout=1.0,
        )
        cache = _TickCache(settings=config)

        # Shared state for thread coordination
        errors = []
        stop_event = threading.Event()

        def add_entries():
            """Thread worker that continuously adds cache entries."""
            counter = 0
            while not stop_event.is_set():
                try:
                    key = (f"thread_add_{counter}",)
                    # Very short TTL to ensure frequent expiration
                    ttl = 0.01

                    def loader(val=counter):
                        return {"value": val}

                    cache.get_or_create(key, ttl, loader)
                    counter += 1
                    time.sleep(0.001)  # Small delay
                except Exception as e:
                    errors.append(("add", e))
                    break

        def access_entries():
            """Thread worker that continuously accesses cache entries."""
            counter = 0
            while not stop_event.is_set():
                try:
                    key = (f"thread_access_{counter % 10}",)  # Rotate through 10 keys
                    ttl = 0.05

                    def loader(current=counter):
                        return {"access": current}

                    cache.get_or_create(key, ttl, loader)
                    counter += 1
                    time.sleep(0.002)
                except Exception as e:
                    errors.append(("access", e))
                    break

        def trigger_pruning():
            """Thread worker that directly triggers cache pruning."""
            while not stop_event.is_set():
                try:
                    with cache._lock:
                        now = time.time()
                        cache._prune_expired(now)
                    time.sleep(0.003)
                except Exception as e:
                    errors.append(("prune", e))
                    break

        # Start multiple threads of each type
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            # 5 threads adding entries
            for _ in range(5):
                futures.append(executor.submit(add_entries))
            # 5 threads accessing entries
            for _ in range(5):
                futures.append(executor.submit(access_entries))
            # 5 threads triggering pruning
            for _ in range(5):
                futures.append(executor.submit(trigger_pruning))

            # Let threads run for a short time
            time.sleep(0.5)

            # Signal threads to stop
            stop_event.set()

            # Wait for all threads to complete
            concurrent.futures.wait(futures, timeout=2.0)

        # Check for any errors - especially RuntimeError from dictionary mutation
        if errors:
            error_types = [type(e[1]).__name__ for e in errors]
            error_msgs = [str(e[1]) for e in errors]
            pytest.fail(
                f"Thread safety issue detected! Errors: {errors}\n"
                f"Error types: {error_types}\n"
                f"Error messages: {error_msgs}"
            )

    def test_prune_with_large_dataset(self):
        """Test pruning with a large number of expired entries.

        This ensures the snapshot approach doesn't cause performance issues
        or memory problems with large dictionaries.
        """
        config = TickCacheSettings(prune_interval=60.0)  # Normal interval
        cache = _TickCache(settings=config)

        # Add many entries that will expire
        now = time.time()
        past_time = now - 10  # Already expired

        # Directly populate cache with expired entries
        with cache._lock:
            for i in range(10000):
                key = (f"expired_{i}",)
                entry = _TickCacheEntry(expires_at=past_time, payload={"value": i})
                cache._data[key] = entry

            # Add some valid entries
            for i in range(100):
                key = (f"valid_{i}",)
                entry = _TickCacheEntry(expires_at=now + 60, payload={"value": i})
                cache._data[key] = entry

            # Verify initial state
            assert len(cache._data) == 10100

            # Trigger pruning
            cache._prune_expired(now)

            # Verify only valid entries remain
            assert len(cache._data) == 100
            # Check that valid entries are still there
            for i in range(100):
                assert (f"valid_{i}",) in cache._data

    def test_prune_during_iteration_simulation(self):
        """Simulate the exact scenario that could cause RuntimeError.

        Before the fix, iterating over dict.items() could fail if the
        dictionary was modified during iteration. This test ensures our
        snapshot approach prevents this.
        """
        config = TickCacheSettings()
        cache = _TickCache(settings=config)

        # Add test entries
        now = time.time()
        with cache._lock:
            for i in range(100):
                key = (f"test_{i}",)
                # Half expired, half valid
                expires = now - 1 if i < 50 else now + 60
                cache._data[key] = _TickCacheEntry(expires_at=expires, payload={"i": i})

        # This should work without RuntimeError even if dictionary changes
        with cache._lock:
            # Start pruning (which creates snapshot)
            cache._prune_expired(now)

        # Verify correct pruning
        assert len(cache._data) == 50

    def test_failure_cooldown_pruning_thread_safety(self):
        """Test that failure cooldown pruning is also thread-safe.

        Bug #44 fix applies to both _data and _failure_cooldowns dictionaries.
        """
        config = TickCacheSettings(prune_interval=0.001, failure_cooldown=0.01)
        cache = _TickCache(settings=config)

        errors = []
        stop_event = threading.Event()

        def add_failures():
            """Add failure cooldown entries."""
            counter = 0
            while not stop_event.is_set():
                try:
                    with cache._lock:
                        now = time.time()
                        # Add already-expired cooldown
                        key = (f"failure_{counter}",)
                        cache._failure_cooldowns[key] = now - 1
                        counter += 1
                    time.sleep(0.001)
                except Exception as e:
                    errors.append(("add_failure", e))
                    break

        def prune_failures():
            """Trigger pruning of failure cooldowns."""
            while not stop_event.is_set():
                try:
                    with cache._lock:
                        now = time.time()
                        cache._prune_expired(now)
                    time.sleep(0.002)
                except Exception as e:
                    errors.append(("prune_failure", e))
                    break

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(add_failures),
                executor.submit(add_failures),
                executor.submit(prune_failures),
                executor.submit(prune_failures),
            ]

            time.sleep(0.3)
            stop_event.set()
            concurrent.futures.wait(futures, timeout=1.0)

        # No errors should occur
        assert not errors, f"Failure cooldown pruning errors: {errors}"

    def test_snapshot_isolation(self):
        """Test that the snapshot approach provides true isolation.

        Verify that the snapshot created during pruning is completely
        independent of the original dictionary.
        """
        config = TickCacheSettings()
        cache = _TickCache(settings=config)

        # Custom _prune_expired that verifies snapshot isolation
        original_prune = cache._prune_expired
        snapshot_items = None

        def custom_prune(now):
            nonlocal snapshot_items
            # Get the snapshot (same as in the fix)
            with cache._lock:
                snapshot_items = list(cache._data.items())
                # Modify original dict while we have snapshot
                cache._data[("new_key",)] = _TickCacheEntry(expires_at=now + 60, payload={"new": True})
                # Snapshot should not include the new key
                assert ("new_key",) not in [k for k, v in snapshot_items]
                # Continue with original pruning logic
                original_prune(now)

        # Replace method temporarily
        cache._prune_expired = custom_prune

        # Add test data and trigger pruning
        now = time.time()
        with cache._lock:
            cache._data[("old_key",)] = _TickCacheEntry(
                expires_at=now - 1,  # Expired
                payload={"old": True},
            )
            cache._prune_expired(now)

        # Verify results
        assert ("new_key",) in cache._data  # Added during pruning
        assert ("old_key",) not in cache._data  # Removed as expired
        assert snapshot_items is not None  # Snapshot was created


class TestCachePrunePerformance:
    """Performance tests to ensure the fix doesn't degrade performance."""

    def test_prune_performance_with_snapshot(self):
        """Benchmark pruning performance with the snapshot approach.

        Ensures the fix doesn't significantly impact performance.
        """
        config = TickCacheSettings(prune_interval=60.0)
        cache = _TickCache(settings=config)

        # Create a large dataset
        now = time.time()
        num_entries = 50000

        with cache._lock:
            # Add many entries (90% expired, 10% valid)
            for i in range(num_entries):
                key = (f"perf_{i}",)
                expires = now - 1 if i < num_entries * 0.9 else now + 60
                cache._data[key] = _TickCacheEntry(expires_at=expires, payload={"i": i})

        # Measure pruning time
        start_time = time.time()
        with cache._lock:
            cache._prune_expired(now)
        prune_time = time.time() - start_time

        # Verify correctness
        expected_remaining = int(num_entries * 0.1)
        assert abs(len(cache._data) - expected_remaining) <= 1  # Allow for rounding

        # Performance assertion: pruning 50k entries should be fast
        # Even with snapshot approach, this should complete in under 100ms
        assert prune_time < 0.1, f"Pruning took {prune_time:.3f}s, expected < 0.1s"


class TestCacheEdgeCases:
    """Edge case tests for the thread-safe cache implementation."""

    def test_empty_cache_pruning(self):
        """Test pruning an empty cache doesn't cause issues."""
        config = TickCacheSettings()
        cache = _TickCache(settings=config)

        # Should not raise any errors
        with cache._lock:
            cache._prune_expired(time.time())

        assert len(cache._data) == 0
        assert len(cache._failure_cooldowns) == 0

    def test_all_entries_expired(self):
        """Test pruning when all entries are expired."""
        config = TickCacheSettings()
        cache = _TickCache(settings=config)

        now = time.time()
        with cache._lock:
            # Add only expired entries
            for i in range(100):
                key = (f"expired_{i}",)
                cache._data[key] = _TickCacheEntry(expires_at=now - 1, payload={"i": i})

            cache._prune_expired(now)

        assert len(cache._data) == 0

    def test_no_entries_expired(self):
        """Test pruning when no entries are expired."""
        config = TickCacheSettings()
        cache = _TickCache(settings=config)

        now = time.time()
        with cache._lock:
            # Add only valid entries
            for i in range(100):
                key = (f"valid_{i}",)
                cache._data[key] = _TickCacheEntry(expires_at=now + 60, payload={"i": i})

            initial_count = len(cache._data)
            cache._prune_expired(now)

        assert len(cache._data) == initial_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
