#!/usr/bin/env python3
"""Interactive Brokers performance monitor."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from datetime import datetime

try:  # pragma: no cover - execution via scripts/
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
    from optipanel.monitoring.pacing import evaluate_pacing_alerts
except ImportError:  # pragma: no cover - adjust sys.path when run directly
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
    from optipanel.monitoring.pacing import evaluate_pacing_alerts


class PerformanceMonitor:
    """Real-time performance monitoring for IBKR connection."""

    def __init__(self):
        self.fetcher: RealTwsFetcher | None = None
        self.running = False
        self.thread: threading.Thread | None = None

        # Metrics tracking
        self.request_times = deque(maxlen=100)  # Last 100 request times
        self.latencies = deque(maxlen=100)  # Last 100 latencies
        self.error_count = 0
        self.total_requests = 0
        self.cache_hits = 0
        self.last_cache_size = 0

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

    def measure_latency(self, symbols: list[str]) -> float:
        """Measure request latency."""
        start = time.perf_counter()
        try:
            self.fetcher.features_for_symbols(symbols)
            latency = (time.perf_counter() - start) * 1000
            self.latencies.append(latency)
            self.request_times.append(time.time())
            self.total_requests += 1
            return latency
        except Exception:
            self.error_count += 1
            return -1

    def get_request_rate(self) -> float:
        """Calculate current request rate per second."""
        if len(self.request_times) < 2:
            return 0

        now = time.time()
        recent = [t for t in self.request_times if now - t <= 10]  # Last 10 seconds

        if len(recent) < 2:
            return 0

        time_span = now - recent[0]
        return len(recent) / time_span if time_span > 0 else 0

    def get_latency_stats(self) -> dict:
        """Get latency statistics."""
        if not self.latencies:
            return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0}

        sorted_lat = sorted(self.latencies)
        n = len(sorted_lat)

        return {
            "avg": sum(self.latencies) / n,
            "min": sorted_lat[0],
            "max": sorted_lat[-1],
            "p50": sorted_lat[n // 2],
            "p95": sorted_lat[int(n * 0.95)] if n > 1 else sorted_lat[0],
        }

    def get_memory_usage_mb(self) -> float:
        """Get memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0

    def clear_screen(self):
        """Clear terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

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
        error_rate = (self.error_count / self.total_requests * 100) if self.total_requests > 0 else 0

        print("\n📊 REQUEST METRICS")
        print(f"  Total Requests: {self.total_requests}")
        print(f"  Request Rate: {request_rate:.2f} req/sec")
        print(f"  Error Rate: {error_rate:.1f}% ({self.error_count} errors)")

        # Latency stats
        lat_stats = self.get_latency_stats()
        print("\n⚡ LATENCY (ms)")
        print(f"  Average: {lat_stats['avg']:.2f}")
        print(f"  Min: {lat_stats['min']:.2f}")
        print(f"  Max: {lat_stats['max']:.2f}")
        print(f"  P50: {lat_stats['p50']:.2f}")
        print(f"  P95: {lat_stats['p95']:.2f}")

        # Cache metrics
        if self.fetcher:
            cache_size = self.fetcher.daily_cache_len()
            cache_efficiency = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0

            print("\n💾 CACHE")
            print(f"  Entries: {cache_size}/{self.fetcher.cfg.daily_max_entries}")
            print(f"  Efficiency: {cache_efficiency:.1f}%")

            # Update cache hit tracking
            if cache_size > self.last_cache_size:
                self.cache_hits += 1
            self.last_cache_size = cache_size

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
