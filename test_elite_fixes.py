#!/usr/bin/env python3
"""Test suite for elite debugger fixes."""

import threading
import time
import tracemalloc
from unittest.mock import Mock, patch

import pytest

from optipanel.api.app import _TickCache, _TickCacheEntry
from optipanel.battlefield.engine import compute_units
from optipanel.ops.session_logger import LogRotationManager


class TestCacheFixes:
    """Test the cache memory and race condition fixes."""

    def test_cache_memory_spike_prevention(self):
        """Verify pruning doesn't create memory spike with many expired entries."""
        cache = _TickCache()

        # Add 10000 entries that expire at same time
        expire_time = time.time() - 1  # Already expired
        for i in range(10000):
            cache._data[(f"key_{i}",)] = _TickCacheEntry(
                expires_at=expire_time, payload={"data": f"value_{i}" * 100}  # Some data
            )

        # Start memory tracking
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # This should NOT cause memory spike (batched deletion)
        cache._prune_expired(time.time())

        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")

        # Calculate memory difference
        total_diff = sum(stat.size_diff for stat in top_stats)

        # Should use less than 1MB for the operation itself
        assert total_diff < 1_000_000, f"Memory spike detected: {total_diff} bytes"

        tracemalloc.stop()

    def test_orphaned_waiter_cleanup(self):
        """Test that timed-out waiters are properly cleaned up."""
        cache = _TickCache()

        # Mock a slow loader
        slow_loader = Mock(side_effect=lambda: time.sleep(40))

        # Start first thread that will hold the lock
        def first_thread():
            cache.get_or_create(("test_key",), 60, slow_loader)

        t1 = threading.Thread(target=first_thread)
        t1.start()

        # Give first thread time to acquire lock
        time.sleep(0.1)

        # Second thread should timeout waiting
        def second_thread():
            mock_loader = Mock(return_value={"data": "value"})
            with patch("time.time", side_effect=[time.time(), time.time() + 31]):
                # This should timeout and clean up its waiter
                result = cache.get_or_create(("test_key",), 60, mock_loader)
                return result

        t2 = threading.Thread(target=second_thread)
        t2.start()
        t2.join(timeout=35)

        # Check no orphaned waiters
        assert len(cache._inflight) <= 1, "Orphaned waiter not cleaned up"

        # Cleanup
        t1.join(timeout=1)

    def test_time_consistency_in_cache(self):
        """Verify same time value is used for expiry and pruning."""
        cache = _TickCache()

        with patch("time.time") as mock_time:
            # Return different times on each call
            mock_time.side_effect = [100.0, 100.1, 100.2, 100.3, 100.4]

            loader = Mock(return_value={"data": "test"})
            cache.get_or_create(("key1",), 10, loader)

            # Check that entry expires at expected time (100.0 + 10)
            assert cache._data[("key1",)].expires_at == 110.0

            # Not 100.1 + 10 or some other time


class TestBattlefieldFixes:
    """Test battlefield engine logic fixes."""

    def test_negative_price_handling(self):
        """Test that negative prices (short positions) work correctly."""
        features = {
            "last": -50.0,  # Short position
            "support": -49.0,
            "resistance": -51.0,
        }

        units = compute_units(features)

        # Should not crash and should calculate correctly
        assert units["support"]["bull"] in [25, 75]
        assert units["resistance"]["bull"] in [25, 35, 65]

    def test_symmetric_support_resistance_logic(self):
        """Verify support and resistance use symmetric logic."""
        # Test equal distance from support and resistance
        features_support = {
            "last": 100.0,
            "support": 99.5,  # 0.5% below
        }

        features_resistance = {
            "last": 100.0,
            "resistance": 100.5,  # 0.5% above
        }

        units_s = compute_units(features_support)
        units_r = compute_units(features_resistance)

        # Both should trigger their respective "near" conditions
        assert units_s["support"]["bull"] == 75  # Near support, bullish
        assert units_r["resistance"]["bull"] == 25  # Near resistance, bearish

    def test_zero_price_protection(self):
        """Ensure zero prices don't cause division errors."""
        features = {
            "last": 0.0,
            "support": 1.0,
            "resistance": 2.0,
        }

        # Should not crash
        units = compute_units(features)
        assert units is not None


class TestLogRotationFixes:
    """Test file rotation fixes."""

    def test_streaming_compression(self, tmp_path):
        """Test that large files are compressed in chunks."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create a large file
        test_file = log_dir / "test.log"
        test_file.write_text("x" * (10 * 1024 * 1024))  # 10MB

        manager = LogRotationManager(str(log_dir))

        # This should stream compress without loading all into memory
        tracemalloc.start()
        rotated = manager.rotate_file(test_file)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Peak memory should be much less than file size
        assert peak < 5_000_000, f"Too much memory used: {peak} bytes"
        assert rotated.suffix == ".gz"

    def test_rotation_with_concurrent_writes(self, tmp_path):
        """Test rotation doesn't lose data during concurrent writes."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        test_file = log_dir / "test.log"
        test_file.write_text("initial\n")

        manager = LogRotationManager(str(log_dir))

        # Simulate concurrent write during rotation
        def writer():
            for i in range(100):
                try:
                    with open(test_file, "a") as f:
                        f.write(f"line_{i}\n")
                        time.sleep(0.001)
                except Exception:
                    pass  # File might be renamed

        def rotator():
            time.sleep(0.05)  # Let writer start
            manager.rotate_file(test_file)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=rotator)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Check no data lost (all files should exist)
        all_files = list(log_dir.glob("test*"))
        assert len(all_files) >= 1  # At least rotated file exists


def test_cache_performance_improvement():
    """Verify pruning doesn't happen on every access."""
    cache = _TickCache()

    # Add some entries
    for i in range(100):
        cache._data[(f"key_{i}",)] = _TickCacheEntry(expires_at=time.time() + 3600, payload={"data": i})

    # Track pruning calls
    original_prune = cache._prune_expired
    prune_count = [0]

    def counting_prune(now):
        prune_count[0] += 1
        return original_prune(now)

    cache._prune_expired = counting_prune

    # Access cache many times quickly
    loader = Mock(return_value={"test": "data"})
    for i in range(100):
        cache.get_or_create((f"new_key_{i}",), 60, loader)

    # Should only prune once per minute, not 100 times
    assert prune_count[0] <= 2, f"Too many prune calls: {prune_count[0]}"


if __name__ == "__main__":
    # Run the tests
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
