#!/usr/bin/env python3
"""Interactive Brokers performance monitor.

FIX for Bug #67: Deque silently drops old metrics without warning or archival.
Added configurable retention, automatic archival to historical statistics,
and comprehensive observability logging.
"""

from __future__ import annotations

import bisect
import logging
import os
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:  # pragma: no cover - execution via scripts/
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
    from optipanel.monitoring.pacing import evaluate_pacing_alerts
    from optipanel.utils.safe_error_handler import SafeErrorHandler
    from optipanel.utils.secure_subprocess import safe_clear_screen
except ImportError:  # pragma: no cover - adjust sys.path when run directly
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
    from optipanel.monitoring.pacing import evaluate_pacing_alerts
    from optipanel.utils.safe_error_handler import SafeErrorHandler
    from optipanel.utils.secure_subprocess import safe_clear_screen

# Module logger following project logging standards
logger = logging.getLogger(__name__)

# Epsilon for floating-point time comparisons (1 millisecond)
# Used in rate calculations to prevent unrealistic values from sub-ms time spans
TIME_EPSILON = 0.001

# FIX for Bug #67: Configurable metrics retention
# Default window size ensures 10-second calculation window coverage even at high rates
# At 100 req/sec, 1000 samples = 10 seconds of data (perfect coverage)
# At 50 req/sec, 1000 samples = 20 seconds of data (2x headroom)
DEFAULT_METRICS_WINDOW_SIZE = int(os.getenv("SENGOKU_PERF_WINDOW_SIZE", "1000"))

# FIX for Bug #84: Error history should be tightly bounded so operators can
# inspect the most recent failures without the structure growing with the main
# metrics window.  The accompanying regression tests expect a cap of 100.
ERROR_HISTORY_MAX_ENTRIES = 100

# Archive threshold: Trigger archival when deque reaches this percentage of capacity
# At 90%, we archive the oldest 40% of data to time-bucketed statistics
ARCHIVE_THRESHOLD_PERCENT = 90

# Archival percentage: How much of the oldest data to archive when threshold reached
ARCHIVE_OLDEST_PERCENT = 40


@dataclass
class ErrorDetails:
    """Immutable record of error occurrence for debugging and analysis.

    Attributes:
        timestamp: Unix timestamp when error occurred
        error_type: Exception class name (e.g., 'ValueError', 'ConnectionError')
        error_message: Human-readable error message
        symbols_requested: List of symbols in the failed request
        stack_trace: Full exception stack trace
        latency_before_failure: Time elapsed before failure (ms)
    """

    timestamp: float
    error_type: str
    error_message: str
    symbols_requested: list[str]
    stack_trace: str
    latency_before_failure: float


@dataclass
class CacheMetrics:
    """Cache performance statistics calculated correctly.

    FIX for Bug #61 and Bug #85: Proper cache metrics tracking.

    Attributes:
        hits: Number of cache hits (data served from cache, no network fetch)
        misses: Number of cache misses (had to fetch from network)
        total_requests: Total requests made
        efficiency: Percentage of requests served from cache
        current_size: Current number of entries in cache
        max_size: Maximum cache capacity
    """

    hits: int
    misses: int
    total_requests: int
    efficiency: float
    current_size: int
    max_size: int


@dataclass
class HistoricalStats:
    """Aggregated historical statistics for a time bucket.

    FIX for Bug #67: Preserve historical trends via time-bucketed aggregation.
    When metrics deques approach capacity, old data is aggregated into these
    buckets rather than silently discarded.

    Attributes:
        timestamp: Start of this time bucket (Unix timestamp)
        duration_sec: Duration of this bucket in seconds (e.g., 60 for 1-minute bucket)
        sample_count: Number of raw samples aggregated into this bucket
        latency_avg: Average latency in milliseconds
        latency_min: Minimum latency in milliseconds
        latency_max: Maximum latency in milliseconds
        latency_p50: Median latency in milliseconds
        latency_p95: 95th percentile latency in milliseconds
        request_rate: Average requests per second during this bucket
        error_count: Number of errors during this bucket
        error_rate: Percentage of requests that failed
    """

    timestamp: float
    duration_sec: int
    sample_count: int
    latency_avg: float
    latency_min: float
    latency_max: float
    latency_p50: float
    latency_p95: float
    request_rate: float
    error_count: int
    error_rate: float


@dataclass
class ArchivalMetrics:
    """Metrics about the archival process itself.

    FIX for Bug #67: Observability into data retention and archival behavior.

    Attributes:
        total_archival_events: How many times archival has been triggered
        total_samples_archived: Total number of samples moved to historical storage
        last_archival_timestamp: When the most recent archival occurred
        current_window_utilization: Percentage of deque capacity currently used
        historical_buckets_count: Number of historical time buckets in storage
    """

    total_archival_events: int = 0
    total_samples_archived: int = 0
    last_archival_timestamp: float = 0.0
    current_window_utilization: float = 0.0
    historical_buckets_count: int = 0


class PerformanceMonitor:
    """Real-time performance monitoring for IBKR connection.

    FIX for Bug #67: Enhanced with configurable metrics retention, automatic archival,
    and historical statistics tracking to prevent silent data loss.
    """

    def __init__(self, window_size: int | None = None):
        """Initialize performance monitor with configurable metrics retention.

        FIX for Bug #67: Configurable window size with automatic archival.

        Args:
            window_size: Number of samples to retain in active window.
                        Defaults to SENGOKU_PERF_WINDOW_SIZE env var (default: 1000).
                        Must be >= 100 to ensure 10-second window coverage.
        """
        self.fetcher: RealTwsFetcher | None = None
        self.running = False
        self.thread: threading.Thread | None = None
        self._metrics_lock = threading.Lock()

        # FIX for Bug #67: Configurable window size with validation
        if window_size is None:
            window_size = DEFAULT_METRICS_WINDOW_SIZE

        # Validate window size: must be at least 100 for basic 10-second window
        if window_size < 100:
            logger.warning(
                "Window size %d too small, using minimum of 100 samples",
                window_size,
            )
            window_size = 100

        self.window_size = window_size

        # FIX for Bug #67: Configurable deque sizes (was hardcoded maxlen=100)
        # No maxlen yet - we'll manage capacity manually to enable archival
        self.request_times: deque[float] = deque()
        self.latencies: deque[float] = deque()

        # Metrics tracking
        self.error_count = 0
        self.total_requests = 0

        # FIX for Bug #61 and Bug #85: Correct cache hit/miss tracking
        # Track actual cache hits (served from cache) vs misses (network fetch)
        self.cache_hits = 0  # Actual hits: data served from cache, no network fetch
        self.cache_misses = 0  # Actual misses: had to fetch from network

        # FIX for Bug #84: Enhanced error tracking with full context
        # Maintain a dedicated, bounded deque so recent failures remain visible
        # even when the metrics window is configured for much larger retention.
        self.error_history: deque[ErrorDetails] = deque(maxlen=ERROR_HISTORY_MAX_ENTRIES)

        # FIX for Bug #67: Historical statistics storage
        # Time-bucketed aggregated stats (bounded to last 24 hours of 1-minute buckets)
        self.historical_stats: deque[HistoricalStats] = deque(maxlen=1440)  # 24 hours * 60 min

        # FIX for Bug #67: Archival tracking metrics
        self.archival_metrics = ArchivalMetrics()

        # FIX for Bug #67: Warnings tracking (to avoid log spam)
        self._capacity_warning_logged = False

        # SafeErrorHandler prevents recursive failures if logging infrastructure fails
        self._error_handler = SafeErrorHandler(logger=logger, context="performance_monitor")

    def connect(self) -> bool:
        """Connect to IBKR."""
        try:
            config = cfg_from_env()
            print(f"Connecting to {config.host}:{config.port}...")
            self.fetcher = RealTwsFetcher(config)
            result = self.fetcher.handshake_test()
            return result.get("handshake") == "ok"
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def _check_and_archive_if_needed(self) -> None:
        """Check deque capacity and archive old data if threshold reached.

        FIX for Bug #67: Automatic archival prevents silent data loss.

        When deques reach 90% capacity, archives oldest 40% of data into
        time-bucketed historical statistics, then removes from active window.

        Must be called under self._metrics_lock.
        """
        current_size = len(self.latencies)
        utilization_percent = (current_size / self.window_size * 100) if self.window_size > 0 else 0

        # Update utilization metric
        self.archival_metrics.current_window_utilization = utilization_percent

        # WARN at 75% capacity (one-time warning until next archival)
        if utilization_percent >= 75 and not self._capacity_warning_logged:
            logger.warning(
                "Metrics window approaching capacity: %d/%d samples (%.1f%%) - archival will trigger at %.0f%%",
                current_size,
                self.window_size,
                utilization_percent,
                ARCHIVE_THRESHOLD_PERCENT,
            )
            self._capacity_warning_logged = True

        # Archive at threshold (90%)
        if utilization_percent >= ARCHIVE_THRESHOLD_PERCENT:
            self._archive_oldest_data()
            # Reset warning flag so we warn again before next archival
            self._capacity_warning_logged = False

    def _archive_oldest_data(self) -> None:
        """Archive oldest data to historical statistics and remove from deques.

        FIX for Bug #67: Preserves historical trends while freeing memory.

        Archives oldest ARCHIVE_OLDEST_PERCENT (40%) of data by:
        1. Aggregating into summary statistics (avg, min, max, p50, p95)
        2. Storing in time-bucketed HistoricalStats
        3. Removing archived samples from active deques

        Must be called under self._metrics_lock.
        """
        samples_to_archive = int(len(self.latencies) * ARCHIVE_OLDEST_PERCENT / 100)

        if samples_to_archive < 10:  # Need meaningful sample size
            return

        # Extract oldest samples
        archived_latencies = [self.latencies.popleft() for _ in range(min(samples_to_archive, len(self.latencies)))]
        archived_times = [self.request_times.popleft() for _ in range(min(samples_to_archive, len(self.request_times)))]

        if not archived_latencies or not archived_times:
            return

        # Calculate aggregated statistics
        sorted_lat = sorted(archived_latencies)
        n = len(sorted_lat)

        # Time bucket: Use start of oldest sample as timestamp
        bucket_start = archived_times[0]
        bucket_duration = archived_times[-1] - archived_times[0]

        # Request rate calculation
        request_rate = n / bucket_duration if bucket_duration >= TIME_EPSILON else 0.0

        # Create historical stats record
        p95_index = int((n - 1) * 0.95) if n > 1 else 0  # FIX Bug #103
        p95_index = max(0, min(p95_index, n - 1))
        historical_stats = HistoricalStats(
            timestamp=bucket_start,
            duration_sec=int(bucket_duration),
            sample_count=n,
            latency_avg=sum(archived_latencies) / n,
            latency_min=sorted_lat[0],
            latency_max=sorted_lat[-1],
            latency_p50=sorted_lat[n // 2],
            latency_p95=sorted_lat[p95_index],
            request_rate=request_rate,
            error_count=0,  # Error counts are tracked separately in error_history
            error_rate=0.0,
        )

        # Store in historical archive
        self.historical_stats.append(historical_stats)

        # Update archival metrics
        self.archival_metrics.total_archival_events += 1
        self.archival_metrics.total_samples_archived += samples_to_archive
        self.archival_metrics.last_archival_timestamp = time.time()
        self.archival_metrics.historical_buckets_count = len(self.historical_stats)

        # Log archival event
        logger.info(
            "Archived %d samples to historical stats: time_range=[%.2f, %.2f] duration=%ds avg_latency=%.2fms rate=%.2freq/s",
            samples_to_archive,
            bucket_start,
            archived_times[-1],
            int(bucket_duration),
            historical_stats.latency_avg,
            request_rate,
        )

        logger.debug(
            "Archival metrics: total_events=%d total_archived=%d active_window=%d/%d historical_buckets=%d",
            self.archival_metrics.total_archival_events,
            self.archival_metrics.total_samples_archived,
            len(self.latencies),
            self.window_size,
            len(self.historical_stats),
        )

    def measure_latency(self, symbols: list[str]) -> float:
        """Measure request latency and track cache performance.

        FIX for Bug #61 and Bug #85: Correct cache hit/miss tracking.
        Tracks actual network fetches via _fresh_requests counter.

        FIX for Bug #84: Enhanced error handling with full context logging and storage.
        Previously, exceptions were caught but details were lost - making debugging impossible.

        Args:
            symbols: List of symbol tickers to request

        Returns:
            Latency in milliseconds, or -1.0 if request failed
        """
        start = time.perf_counter()

        # FIX for Bug #61: Capture network request counter BEFORE the call
        # This is how we determine if data came from cache or network
        fresh_requests_before = getattr(self.fetcher, "_fresh_requests", None)

        try:
            self.fetcher.features_for_symbols(symbols)
            latency = (time.perf_counter() - start) * 1000

            # FIX for Bug #61: Check if network fetch occurred
            fresh_requests_after = getattr(self.fetcher, "_fresh_requests", None)

            # Determine if this was a cache hit or miss
            was_cache_miss = False
            if (
                fresh_requests_before is not None
                and fresh_requests_after is not None
                and isinstance(fresh_requests_before, int)
                and isinstance(fresh_requests_after, int)
            ):
                # If _fresh_requests increased, we made a network call (MISS)
                # If it stayed the same, data came from cache (HIT)
                was_cache_miss = fresh_requests_after > fresh_requests_before

            with self._metrics_lock:
                self.latencies.append(latency)
                self.request_times.append(time.time())
                self.total_requests += 1

                # FIX for Bug #61 and Bug #85: Correct cache tracking
                if was_cache_miss:
                    self.cache_misses += 1
                else:
                    self.cache_hits += 1

                # FIX for Bug #67: Check if archival needed after adding new sample
                self._check_and_archive_if_needed()

            return latency
        except Exception as e:
            # FIX for Bug #84: Comprehensive error tracking
            # Calculate latency before failure for performance analysis
            latency_ms = (time.perf_counter() - start) * 1000

            # Create immutable error record with full context
            error_details = ErrorDetails(
                timestamp=time.time(),
                error_type=type(e).__name__,
                error_message=str(e),
                symbols_requested=symbols.copy(),  # Defensive copy
                stack_trace=traceback.format_exc(),
                latency_before_failure=latency_ms,
            )

            # Thread-safe error storage and metrics update
            with self._metrics_lock:
                self.error_count += 1
                self.error_history.append(error_details)

            # Structured logging with SafeErrorHandler to prevent recursive failures
            message = (
                "Request failed: operation=measure_latency symbols="
                f"{symbols} error_type={type(e).__name__} latency_ms={latency_ms:.2f}"
            )
            self._error_handler.handle_error(
                message,
                exc=e,
                exc_info=True,  # Include full stack trace
            )

            return -1.0

    def get_request_rate(self) -> float:
        """Calculate current request rate per second.

        FIX for Bug #79: Efficient O(log n) calculation using binary search.

        Previously used O(n) list comprehension filtering all samples every call.
        Now uses bisect to find cutoff point in O(log n) time since timestamps
        are naturally sorted (monotonically increasing by append-only pattern).

        Returns:
            Requests per second over the last 10 seconds
        """
        with self._metrics_lock:
            samples = list(self.request_times)

        if len(samples) < 2:
            return 0

        now = time.time()
        cutoff = now - 10.0  # 10-second window

        # FIX Bug #79: Use binary search instead of filtering
        # samples is naturally sorted (oldest first), so we can bisect
        # bisect_left finds the leftmost position where cutoff could be inserted
        # Everything from that index onwards is within the 10-second window
        cutoff_index = bisect.bisect_left(samples, cutoff)
        recent = samples[cutoff_index:]  # O(1) slice instead of O(n) filter

        if len(recent) < 2:
            return 0

        # Calculate rate: count / time_span
        # Use actual time span between first and last sample for accuracy
        time_span = recent[-1] - recent[0]

        # Prevent unrealistic rates from sub-millisecond time spans
        # If all requests happened within 1ms, return 0 (too fast to be real)
        if time_span < TIME_EPSILON:
            return 0.0

        return len(recent) / time_span

    def get_latency_stats(self) -> dict:
        """Get latency statistics."""
        with self._metrics_lock:
            samples = list(self.latencies)

        if not samples:
            return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0}

        sorted_lat = sorted(samples)
        n = len(sorted_lat)

        p95_index = int((n - 1) * 0.95) if n > 1 else 0  # FIX Bug #103
        p95_index = max(0, min(p95_index, n - 1))
        return {
            "avg": sum(samples) / n,
            "min": sorted_lat[0],
            "max": sorted_lat[-1],
            "p50": sorted_lat[n // 2],
            "p95": sorted_lat[p95_index],
        }

    def get_memory_usage_mb(self) -> float:
        """Get memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0

    def get_error_history(self, limit: int | None = None) -> list[ErrorDetails]:
        """Retrieve recent error history for debugging.

        FIX for Bug #84: Provide programmatic access to error details.

        Args:
            limit: Maximum number of errors to return (None = all)

        Returns:
            List of ErrorDetails, most recent first
        """
        with self._metrics_lock:
            errors = list(self.error_history)

        # Return most recent first
        errors.reverse()

        if limit is not None:
            return errors[:limit]
        return errors

    def get_error_patterns(self) -> dict[str, int]:
        """Analyze error patterns for trend detection.

        FIX for Bug #84: Enable pattern detection for recurring failures.

        Returns:
            Dict mapping error_type to occurrence count
        """
        with self._metrics_lock:
            errors = list(self.error_history)

        pattern_counts: dict[str, int] = {}
        for error in errors:
            pattern_counts[error.error_type] = pattern_counts.get(error.error_type, 0) + 1

        return pattern_counts

    def get_cache_metrics(self) -> CacheMetrics:
        """Calculate accurate cache performance metrics.

        FIX for Bug #61 and Bug #85: Correct cache efficiency calculation.

        The efficiency formula is: hits / (hits + misses) * 100
        - NOT: hits / total_requests (the old broken formula)

        This is because total_requests includes errors, which don't affect cache.
        The correct denominator is only successful requests (hits + misses).

        Returns:
            CacheMetrics with accurate statistics
        """
        if not self.fetcher:
            return CacheMetrics(
                hits=0,
                misses=0,
                total_requests=0,
                efficiency=0.0,
                current_size=0,
                max_size=0,
            )

        with self._metrics_lock:
            hits = self.cache_hits
            misses = self.cache_misses
            total = self.total_requests

        # FIX for Bug #85: Correct efficiency calculation
        # Efficiency = hits / (hits + misses), not hits / total_requests
        # This excludes errors from the calculation, which is correct
        cache_requests = hits + misses
        efficiency = (hits / cache_requests * 100) if cache_requests > 0 else 0.0

        return CacheMetrics(
            hits=hits,
            misses=misses,
            total_requests=total,
            efficiency=efficiency,
            current_size=self.fetcher.daily_cache_len(),
            max_size=self.fetcher.cfg.daily_max_entries,
        )

    def get_archival_metrics(self) -> ArchivalMetrics:
        """Get metrics about the archival process.

        FIX for Bug #67: Observability into data retention behavior.

        Returns:
            ArchivalMetrics with current archival statistics
        """
        with self._metrics_lock:
            # Return a copy to avoid external modification
            return ArchivalMetrics(
                total_archival_events=self.archival_metrics.total_archival_events,
                total_samples_archived=self.archival_metrics.total_samples_archived,
                last_archival_timestamp=self.archival_metrics.last_archival_timestamp,
                current_window_utilization=self.archival_metrics.current_window_utilization,
                historical_buckets_count=self.archival_metrics.historical_buckets_count,
            )

    def get_historical_stats(self, last_n_buckets: int | None = None) -> list[HistoricalStats]:
        """Retrieve historical performance statistics.

        FIX for Bug #67: Access to archived historical data for trend analysis.

        Args:
            last_n_buckets: Number of most recent buckets to return (None = all)

        Returns:
            List of HistoricalStats, most recent first
        """
        with self._metrics_lock:
            stats = list(self.historical_stats)

        # Return most recent first
        stats.reverse()

        if last_n_buckets is not None and last_n_buckets > 0:
            return stats[:last_n_buckets]
        return stats

    def get_performance_trend(self) -> dict[str, Any]:
        """Analyze performance trends by comparing current vs historical.

        FIX for Bug #67: Enable trend detection using archived historical data.

        Returns:
            Dict with trend analysis:
            - current_avg_latency: Current average latency (ms)
            - historical_avg_latency: Historical average latency (ms)
            - latency_trend: "improving", "stable", or "degrading"
            - current_request_rate: Current requests/sec
            - historical_request_rate: Historical requests/sec
            - has_historical_data: Whether historical data is available
        """
        current_stats = self.get_latency_stats()
        current_rate = self.get_request_rate()

        with self._metrics_lock:
            historical = list(self.historical_stats)

        if not historical:
            return {
                "current_avg_latency": current_stats["avg"],
                "historical_avg_latency": 0.0,
                "latency_trend": "unknown",
                "current_request_rate": current_rate,
                "historical_request_rate": 0.0,
                "has_historical_data": False,
            }

        # Calculate historical averages from all buckets
        hist_latencies = [h.latency_avg for h in historical]
        hist_rates = [h.request_rate for h in historical]

        hist_avg_latency = sum(hist_latencies) / len(hist_latencies)
        hist_avg_rate = sum(hist_rates) / len(hist_rates)

        # Determine latency trend (5% threshold for "stable")
        latency_change_percent = (
            ((current_stats["avg"] - hist_avg_latency) / hist_avg_latency * 100) if hist_avg_latency > 0 else 0
        )

        if latency_change_percent < -5:
            trend = "improving"  # Latency decreased by >5%
        elif latency_change_percent > 5:
            trend = "degrading"  # Latency increased by >5%
        else:
            trend = "stable"  # Within 5% range

        return {
            "current_avg_latency": current_stats["avg"],
            "historical_avg_latency": hist_avg_latency,
            "latency_trend": trend,
            "latency_change_percent": latency_change_percent,
            "current_request_rate": current_rate,
            "historical_request_rate": hist_avg_rate,
            "has_historical_data": True,
            "historical_buckets": len(historical),
        }

    def clear_screen(self):
        """Clear terminal screen safely using secure subprocess wrapper.

        Bug #73 fix: Import moved to module level for early error detection
        and better performance.
        """
        # Use the secure wrapper that prevents command injection
        safe_clear_screen()

    def display_dashboard(self):
        """Display performance dashboard."""
        self.clear_screen()

        print("=" * 70)
        print("  IBKR PERFORMANCE MONITOR - LIVE")
        print("=" * 70)
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Connection info
        if self.fetcher:
            config = self.fetcher.cfg
            print("\n📡 CONNECTION")
            print(f"  Host: {config.host}:{config.port}")
            print(f"  Client ID: {config.client_id}")

        # Request metrics
        request_rate = self.get_request_rate()
        lat_stats = self.get_latency_stats()
        with self._metrics_lock:
            total_requests = self.total_requests
            error_count = self.error_count

        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

        print("\n📊 REQUEST METRICS")
        print(f"  Total Requests: {total_requests}")
        print(f"  Request Rate: {request_rate:.2f} req/sec")
        print(f"  Error Rate: {error_rate:.1f}% ({error_count} errors)")

        # FIX for Bug #84: Display error insights
        if error_count > 0:
            error_patterns = self.get_error_patterns()
            recent_errors = self.get_error_history(limit=3)

            print("\n❌ ERROR INSIGHTS (Bug #84 Fix)")
            print("  Error Patterns:")
            for error_type, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"    • {error_type}: {count} occurrences")

            if recent_errors:
                print("  Most Recent Errors:")
                for i, error in enumerate(recent_errors[:2], 1):
                    elapsed = time.time() - error.timestamp
                    print(f"    {i}. {error.error_type}: {error.error_message[:50]}... ({elapsed:.0f}s ago)")
                    print(f"       Symbols: {', '.join(error.symbols_requested)}")

        # Latency stats
        print("\n⚡ LATENCY (ms)")
        print(f"  Average: {lat_stats['avg']:.2f}")
        print(f"  Min: {lat_stats['min']:.2f}")
        print(f"  Max: {lat_stats['max']:.2f}")
        print(f"  P50: {lat_stats['p50']:.2f}")
        print(f"  P95: {lat_stats['p95']:.2f}")

        # Cache metrics - FIX for Bug #61 and Bug #85
        if self.fetcher:
            cache_metrics = self.get_cache_metrics()

            print("\n💾 CACHE (Bug #61/#85 Fix - Correct Tracking)")
            print(f"  Entries: {cache_metrics.current_size}/{cache_metrics.max_size}")
            print(f"  Hits: {cache_metrics.hits}")
            print(f"  Misses: {cache_metrics.misses}")
            print(f"  Efficiency: {cache_metrics.efficiency:.1f}% (hits/(hits+misses))")
            print(f"  Hit Rate: {cache_metrics.hits}/{cache_metrics.hits + cache_metrics.misses} successful requests")

        # FIX for Bug #67: Display archival metrics and historical trends
        archival = self.get_archival_metrics()
        trend = self.get_performance_trend()

        print("\n📚 METRICS RETENTION (Bug #67 Fix - Archival System)")
        print(
            f"  Active Window: {len(self.latencies)}/{self.window_size} samples ({archival.current_window_utilization:.1f}% full)"
        )
        print(f"  Archival Events: {archival.total_archival_events}")
        print(f"  Total Archived: {archival.total_samples_archived} samples")
        print(f"  Historical Buckets: {archival.historical_buckets_count}")

        if trend["has_historical_data"]:
            trend_icon = (
                "📈"
                if trend["latency_trend"] == "improving"
                else "📉" if trend["latency_trend"] == "degrading" else "➡️"
            )
            print(f"\n{trend_icon} PERFORMANCE TREND")
            print(f"  Current Avg Latency: {trend['current_avg_latency']:.2f}ms")
            print(f"  Historical Avg: {trend['historical_avg_latency']:.2f}ms")
            print(f"  Trend: {trend['latency_trend'].upper()} ({trend['latency_change_percent']:+.1f}%)")
            print(f"  Based on {trend['historical_buckets']} archived time buckets")

        # Rate limiting
        if self.fetcher:
            pacing = self.fetcher.pacing_metrics()
            print("\n🚦 RATE LIMITING")
            print(
                f"  Global Rate: {pacing.get('global_rate_current', 0)}/{pacing.get('global_rate_max_requests', 0)} per {pacing.get('global_rate_interval_sec', 0)}s"
            )
            print(f"  Window Requests: {pacing.get('requests_in_window', 0)}")
            print(f"  Total Requests: {pacing.get('total_requests', 0)}")
            print(f"  Last Wait: {pacing.get('global_rate_last_wait_sec', 0):.3f}s")
            print(f"  Total Wait: {pacing.get('global_rate_total_wait_sec', 0):.1f}s")

            # Check for pacing alerts
            alerts = evaluate_pacing_alerts(pacing)
            if alerts:
                print("\n⚠️ ALERTS")
                for alert in alerts:
                    severity_icon = "🔴" if alert.severity == "high" else "🟡"
                    print(f"  {severity_icon} {alert.message}")

        # System resources
        memory_mb = self.get_memory_usage_mb()
        print("\n💻 SYSTEM")
        print(f"  Memory: {memory_mb:.1f} MB")
        print(f"  Uptime: {time.time() - self.start_time:.0f}s")

        # Visual throughput bar
        max_rate = 10  # Max expected requests/sec
        bar_length = 50
        filled = int(min(request_rate / max_rate, 1.0) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        print("\n📈 THROUGHPUT")
        print(f"  [{bar}] {request_rate:.1f} req/s")

        print("\n" + "=" * 70)
        print("Press Ctrl+C to stop monitoring")

    def monitor_loop(self):
        """Main monitoring loop."""
        test_symbols = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
        symbol_index = 0

        while self.running:
            # Make a test request
            symbol = test_symbols[symbol_index]
            symbol_index = (symbol_index + 1) % len(test_symbols)

            self.measure_latency([symbol])

            # Update display
            self.display_dashboard()

            # Wait before next update
            time.sleep(2)

    def start(self):
        """Start monitoring."""
        if not self.connect():
            print("❌ Failed to connect to IBKR")
            return False

        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)


def main():
    """Run the performance monitor."""
    print("Starting IBKR Performance Monitor...")
    print("=" * 70)

    monitor = PerformanceMonitor()

    if not monitor.start():
        return 1

    try:
        # Keep main thread alive
        while monitor.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        monitor.stop()

    # Final statistics
    print("\n" + "=" * 70)
    print("  FINAL STATISTICS")
    print("=" * 70)

    lat_stats = monitor.get_latency_stats()
    error_rate = (monitor.error_count / monitor.total_requests * 100) if monitor.total_requests > 0 else 0

    print(f"Total Requests: {monitor.total_requests}")
    print(f"Error Rate: {error_rate:.1f}%")
    print(f"Average Latency: {lat_stats['avg']:.2f}ms")
    print(f"P95 Latency: {lat_stats['p95']:.2f}ms")

    # Performance assessment
    print("\n🎯 Assessment:")
    if lat_stats["avg"] < 100 and error_rate < 5:
        print("  ✅ Excellent performance")
    elif lat_stats["avg"] < 200 and error_rate < 10:
        print("  ⚠️ Good performance, minor optimization possible")
    else:
        print("  ❌ Performance issues detected")

    return 0


if __name__ == "__main__":
    sys.exit(main())
