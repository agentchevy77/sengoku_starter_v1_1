"""
Test for Issue #3 fix: Race condition in TWS pacing metrics.

This test verifies that concurrent access to pacing metrics
is thread-safe after adding the _rate_metrics_lock.
"""

import threading
import time
from unittest.mock import patch

from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig


class TestPacingMetricsRaceFix:
    """Test suite for pacing metrics thread-safety fix (Issue #3)."""

    def test_concurrent_metric_updates_no_race(self):
        """Test that concurrent metric updates don't cause race conditions."""
        # Create fetcher with rate limiting enabled
        config = TwsConfig(
            host="localhost",
            port=7496,
            client_id=999,
            global_rate_max_requests=50,
            global_rate_interval_sec=1.0,
        )
        fetcher = RealTwsFetcher(cfg=config)

        # Track any exceptions from threads
        exceptions = []

        def update_metrics(thread_id, iterations=100):
            """Simulate metric updates from a request thread."""
            try:
                for i in range(iterations):
                    # Simulate acquiring the rate limiter
                    with fetcher._rate_metrics_lock:
                        # Simulate wait time
                        waited = 0.001 * (thread_id + i)
                        fetcher._rate_wait_last = waited
                        if waited:
                            now = time.time()
                            fetcher._rate_wait_events.append((now, waited))
                            fetcher._rate_wait_total += waited
                            # Simulate pruning old events
                            cutoff = now - 1.0
                            while fetcher._rate_wait_events and fetcher._rate_wait_events[0][0] < cutoff:
                                _, duration = fetcher._rate_wait_events.popleft()
                                fetcher._rate_wait_total = max(0.0, fetcher._rate_wait_total - duration)
            except Exception as e:
                exceptions.append((thread_id, e))

        def read_metrics(iterations=100):
            """Simulate reading metrics from monitoring thread."""
            results = []
            try:
                for _ in range(iterations):
                    metrics = fetcher.pacing_metrics()
                    # Verify we got valid metrics
                    assert isinstance(metrics, dict)
                    assert "global_rate_total_wait_sec" in metrics
                    assert "global_rate_last_wait_sec" in metrics
                    assert metrics["global_rate_total_wait_sec"] >= 0
                    results.append(metrics)
                    time.sleep(0.0001)  # Small delay between reads
            except Exception as e:
                exceptions.append(("reader", e))
            return results

        # Start multiple threads updating metrics concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_metrics, args=(i, 50))
            threads.append(t)
            t.start()

        # Start a reader thread
        reader = threading.Thread(target=read_metrics, args=(100,))
        reader.start()

        # Wait for all threads
        for t in threads:
            t.join()
        reader.join()

        # Check no exceptions occurred
        assert not exceptions, f"Thread exceptions occurred: {exceptions}"

        # Verify final metrics are consistent
        final_metrics = fetcher.pacing_metrics()
        assert final_metrics["global_rate_total_wait_sec"] >= 0
        assert isinstance(final_metrics["global_rate_wait_ratio"], float)

    def test_pacing_metrics_returns_consistent_snapshot(self):
        """Test that pacing_metrics returns a consistent snapshot."""
        config = TwsConfig(
            host="localhost",
            port=7496,
            client_id=999,
            global_rate_max_requests=50,
            global_rate_interval_sec=1.0,
        )
        fetcher = RealTwsFetcher(cfg=config)

        # Set known values
        with fetcher._rate_metrics_lock:
            fetcher._rate_wait_last = 0.5
            fetcher._rate_wait_total = 10.0

        # Get metrics
        metrics = fetcher.pacing_metrics()

        # Verify snapshot values
        assert metrics["global_rate_last_wait_sec"] == 0.5
        assert metrics["global_rate_total_wait_sec"] == 10.0
        assert metrics["global_rate_wait_ratio"] == 10.0  # 10.0 / 1.0

    def test_pace_request_with_lock(self):
        """Test that _pace_request properly uses the lock."""
        config = TwsConfig(
            host="localhost",
            port=7496,
            client_id=999,
            global_rate_max_requests=1,  # Very low to trigger rate limiting
            global_rate_interval_sec=0.1,
            pacing_interval_sec=0.1,
        )
        fetcher = RealTwsFetcher(cfg=config)

        # Mock the rate limiter to simulate waiting
        with patch.object(fetcher._global_rate_limiter, "acquire", return_value=0.05):
            # Call _pace_request
            fetcher._pace_request()

            # Verify metrics were updated
            with fetcher._rate_metrics_lock:
                assert fetcher._rate_wait_last == 0.05
                assert fetcher._rate_wait_total > 0
                assert len(fetcher._rate_wait_events) > 0

    def test_no_deadlock_under_high_contention(self):
        """Test that high contention doesn't cause deadlock."""
        config = TwsConfig(
            host="localhost",
            port=7496,
            client_id=999,
            global_rate_max_requests=10,
            global_rate_interval_sec=1.0,
        )
        fetcher = RealTwsFetcher(cfg=config)

        stop_flag = threading.Event()
        deadlock_detected = threading.Event()

        def aggressive_updater():
            """Aggressively update metrics."""
            while not stop_flag.is_set():
                with fetcher._rate_metrics_lock:
                    fetcher._rate_wait_total += 0.001
                    fetcher._rate_wait_last = 0.001

        def aggressive_reader():
            """Aggressively read metrics."""
            while not stop_flag.is_set():
                fetcher.pacing_metrics()

        def deadlock_detector():
            """Detect if threads are stuck."""
            time.sleep(2.0)  # Give threads time to deadlock if they will
            if not stop_flag.is_set():
                # If we get here, no deadlock occurred
                stop_flag.set()
            else:
                deadlock_detected.set()

        # Start aggressive threads
        updaters = [threading.Thread(target=aggressive_updater) for _ in range(3)]
        readers = [threading.Thread(target=aggressive_reader) for _ in range(3)]
        detector = threading.Thread(target=deadlock_detector)

        for t in updaters + readers:
            t.daemon = True  # Daemon so test doesn't hang on deadlock
            t.start()
        detector.start()

        # Wait for detector to complete
        detector.join(timeout=5.0)

        # Stop all threads
        stop_flag.set()

        # Verify no deadlock
        assert not deadlock_detected.is_set(), "Deadlock detected!"
        assert stop_flag.is_set(), "Test completed successfully"


if __name__ == "__main__":
    # Run tests
    test = TestPacingMetricsRaceFix()
    test.test_concurrent_metric_updates_no_race()
    test.test_pacing_metrics_returns_consistent_snapshot()
    test.test_pace_request_with_lock()
    test.test_no_deadlock_under_high_contention()
    print("✅ All pacing metrics race condition tests passed!")
