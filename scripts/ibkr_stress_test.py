#!/usr/bin/env python3
"""IBKR performance & stress test suite."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

try:  # pragma: no cover - execution via scripts/
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig, cfg_from_env
    from optipanel.ops.session_logger import get_session_logger
except ImportError:  # pragma: no cover - adjust sys.path when run directly
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig, cfg_from_env
    from optipanel.ops.session_logger import get_session_logger


@dataclass
class PerformanceMetrics:
    """Track performance metrics during stress test."""

    test_name: str
    start_time: float
    end_time: float
    symbols_tested: int
    requests_made: int
    successful_requests: int
    failed_requests: int
    cache_hits: int
    total_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    requests_per_second: float
    memory_used_mb: float
    rate_limit_waits: int
    total_wait_time_sec: float
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IBKRStressTest:
    """IBKR stress testing framework."""

    def __init__(self, config: TwsConfig | None = None):
        self.config = config or cfg_from_env()
        self.fetcher: RealTwsFetcher | None = None
        self.logger = get_session_logger(command="ibkr_stress_test")
        self.latencies: deque = deque(maxlen=10000)
        self.start_time: float = 0
        self.requests_made: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.errors: deque[str] = deque(maxlen=1000)  # Fixed: bounded to prevent memory leak

    def connect(self) -> bool:
        """Establish connection to IBKR."""
        try:
            print(f"Connecting to IBKR at {self.config.host}:{self.config.port}...")
            self.fetcher = RealTwsFetcher(self.config)
            result = self.fetcher.handshake_test()

            if result.get("handshake") == "ok":
                print("✅ Connected successfully!")
                return True
            else:
                print(f"❌ Handshake failed: {result}")
                return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def measure_request(self, symbols: list[str]) -> float | None:
        """Make a request and measure latency."""
        start = time.perf_counter()
        try:
            features = self.fetcher.features_for_symbols(symbols)
            latency_ms = (time.perf_counter() - start) * 1000

            if features:
                self.successful_requests += 1
                self.latencies.append(latency_ms)
                return latency_ms
            else:
                self.failed_requests += 1
                return None

        except Exception as e:
            self.failed_requests += 1
            self.errors.append(str(e))
            return None
        finally:
            self.requests_made += 1

    def calculate_percentiles(self) -> tuple[float, float, float]:
        """Calculate latency percentiles."""
        if not self.latencies:
            return 0.0, 0.0, 0.0

        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)

        p50 = sorted_latencies[int(n * 0.50)]
        p95 = sorted_latencies[int(n * 0.95)]
        p99 = sorted_latencies[int(n * 0.99)]

        return p50, p95, p99

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)

    def test_symbol_scaling(self, max_symbols: int = 100) -> PerformanceMetrics:
        """Test performance with increasing number of symbols."""
        print(f"\n{'='*60}")
        print(f"  SYMBOL SCALING TEST (up to {max_symbols} symbols)")
        print("=" * 60)

        test_sizes = [10, 25, 50, 75, 100, 150, 200]
        test_sizes = [s for s in test_sizes if s <= max_symbols]

        # Common stock symbols for testing
        all_symbols = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "TSLA",
            "META",
            "BRK.B",
            "JPM",
            "JNJ",
            "V",
            "PG",
            "UNH",
            "HD",
            "MA",
            "DIS",
            "BAC",
            "XOM",
            "PFE",
            "CSCO",
            "ADBE",
            "NFLX",
            "CRM",
            "ABT",
            "NKE",
            "WMT",
            "CVX",
            "PEP",
            "TMO",
            "ABBV",
            "AVGO",
            "COST",
            "KO",
            "MRK",
            "VZ",
            "CMCSA",
            "INTC",
            "WFC",
            "QCOM",
            "T",
            "UPS",
            "TXN",
            "PM",
            "MS",
            "RTX",
            "NEE",
            "BMY",
            "HON",
            "LOW",
            "ORCL",
            "BA",
            "AMD",
            "IBM",
            "GS",
            "CAT",
            "SCHW",
            "C",
            "BLK",
            "AMGN",
            "AXP",
            "GE",
            "GILD",
            "SBUX",
            "ISRG",
            "CVS",
            "DE",
            "MO",
            "BKNG",
            "ADI",
            "TJX",
            "MMC",
            "MDLZ",
            "PLD",
            "CI",
            "TMUS",
            "ZTS",
            "SYK",
            "CB",
            "SO",
            "DUK",
            "CL",
            "VRTX",
            "BSX",
            "BDX",
            "REGN",
            "EOG",
            "CSX",
            "NOC",
            "FCX",
            "HUM",
            "CCI",
            "KLAC",
            "CME",
            "COP",
            "NSC",
            "USB",
            "MCO",
            "MPC",
            "ICE",
            "WM",
            "PNC",
            "GD",
            "MMM",
            "TGT",
            "F",
            "GM",
            "SPY",
            "QQQ",
            "IWM",
            "DIA",
            "VTI",
            "VOO",
            "EEM",
            "GLD",
            "TLT",
            "XLF",
            "XLK",
            "XLE",
            "XLV",
            "XLI",
            "XLY",
            "XLP",
            "XLU",
            "XLB",
            "XLRE",
            "IYR",
            "AGG",
            "HYG",
            "LQD",
            "EMB",
            "MUB",
            "SHY",
            "TIP",
            "VCIT",
            "VCSH",
            "BND",
        ] * 3  # Repeat to ensure we have enough symbols

        self.reset_metrics()
        self.start_time = time.perf_counter()

        for size in test_sizes:
            test_symbols = all_symbols[:size]
            print(f"\nTesting with {size} symbols...")

            with self.logger.operation_context("scale_test", symbol_count=size):
                for i in range(3):  # 3 iterations per size
                    latency = self.measure_request(test_symbols)
                    if latency:
                        print(f"  Iteration {i+1}: {latency:.2f}ms")
                    else:
                        print(f"  Iteration {i+1}: Failed")

                    time.sleep(0.5)  # Small delay between iterations

        return self.create_metrics("Symbol Scaling", max_symbols)

    def test_burst_load(self, duration_sec: int = 30, burst_size: int = 10) -> PerformanceMetrics:
        """Test burst load at maximum rate."""
        print(f"\n{'='*60}")
        print(f"  BURST LOAD TEST ({duration_sec}s, {burst_size} symbols/burst)")
        print("=" * 60)

        symbols = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "SPY", "QQQ", "IWM"][:burst_size]

        self.reset_metrics()
        self.start_time = time.perf_counter()
        end_time = self.start_time + duration_sec

        burst_count = 0
        while time.perf_counter() < end_time:
            burst_count += 1
            print(f"\nBurst #{burst_count}:")

            with self.logger.operation_context("burst_test", burst_num=burst_count):
                # Fire requests as fast as possible
                for i in range(5):  # 5 rapid requests
                    latency = self.measure_request(symbols)
                    if latency:
                        print(f"  Request {i+1}: {latency:.2f}ms")
                    time.sleep(0.05)  # 50ms between requests in burst

            # Check rate limiter status
            if self.fetcher:
                metrics = self.fetcher.pacing_metrics()
                wait_time = metrics.get("global_rate_last_wait_sec", 0)
                if wait_time > 0:
                    print(f"  ⚠️ Rate limiter wait: {wait_time:.2f}s")

            time.sleep(1)  # 1 second between bursts

        return self.create_metrics("Burst Load", burst_size)

    def test_sustained_load(self, duration_sec: int = 300, symbols_per_request: int = 20) -> PerformanceMetrics:
        """Test sustained load over longer period."""
        print(f"\n{'='*60}")
        print(f"  SUSTAINED LOAD TEST ({duration_sec}s, {symbols_per_request} symbols/request)")
        print("=" * 60)

        symbols = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "NVDA",
            "TSLA",
            "META",
            "AMZN",
            "SPY",
            "QQQ",
            "IWM",
            "DIA",
            "VTI",
            "VOO",
            "EEM",
            "GLD",
            "TLT",
            "XLF",
            "XLK",
            "XLE",
            "XLV",
        ][:symbols_per_request]

        self.reset_metrics()
        self.start_time = time.perf_counter()
        end_time = self.start_time + duration_sec

        request_count = 0
        last_report_time = self.start_time

        while time.perf_counter() < end_time:
            request_count += 1

            with self.logger.operation_context("sustained_test", request_num=request_count):
                self.measure_request(symbols)

                # Report every 30 seconds
                current_time = time.perf_counter()
                if current_time - last_report_time >= 30:
                    elapsed = current_time - self.start_time
                    rate = self.requests_made / elapsed if elapsed > 0 else 0
                    success_rate = (
                        (self.successful_requests / self.requests_made * 100) if self.requests_made > 0 else 0
                    )

                    print(f"\nProgress Report ({elapsed:.0f}s):")
                    print(f"  Requests: {self.requests_made}")
                    print(f"  Success rate: {success_rate:.1f}%")
                    print(f"  Request rate: {rate:.2f}/sec")
                    print(f"  Memory: {self.get_memory_usage_mb():.1f} MB")

                    if self.fetcher:
                        cache_len = self.fetcher.daily_cache_len()
                        print(f"  Cache size: {cache_len}")

                    last_report_time = current_time

            # Steady pace to avoid overwhelming
            time.sleep(1.5)

        return self.create_metrics("Sustained Load", symbols_per_request)

    def test_market_open_simulation(self, symbol_count: int = 100) -> PerformanceMetrics:
        """Simulate market open with many symbols requesting data simultaneously."""
        print(f"\n{'='*60}")
        print(f"  MARKET OPEN SIMULATION ({symbol_count} symbols)")
        print("=" * 60)

        # Simulate most active stocks at market open
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPY", "QQQ", "IWM"] * (symbol_count // 10)
        symbols = symbols[:symbol_count]

        self.reset_metrics()
        self.start_time = time.perf_counter()

        print("\nSimulating market open surge...")

        # Split into waves to simulate realistic market open
        wave_size = 25
        waves = [symbols[i : i + wave_size] for i in range(0, len(symbols), wave_size)]

        for wave_num, wave_symbols in enumerate(waves, 1):
            print(f"\nWave {wave_num}/{len(waves)} ({len(wave_symbols)} symbols)...")

            with self.logger.operation_context("market_open_wave", wave=wave_num):
                latency = self.measure_request(wave_symbols)
                if latency:
                    print(f"  Latency: {latency:.2f}ms")
                    print(f"  Throughput: {len(wave_symbols) / (latency/1000):.1f} symbols/sec")

            # Small delay between waves
            if wave_num < len(waves):
                time.sleep(0.5)

        return self.create_metrics("Market Open", symbol_count)

    def reset_metrics(self):
        """Reset metrics for new test."""
        self.latencies.clear()
        self.requests_made = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.errors.clear()

    def create_metrics(self, test_name: str, symbols_tested: int) -> PerformanceMetrics:
        """Create performance metrics from current state."""
        end_time = time.perf_counter()
        elapsed = end_time - self.start_time

        p50, p95, p99 = self.calculate_percentiles()

        return PerformanceMetrics(
            test_name=test_name,
            start_time=self.start_time,
            end_time=end_time,
            symbols_tested=symbols_tested,
            requests_made=self.requests_made,
            successful_requests=self.successful_requests,
            failed_requests=self.failed_requests,
            cache_hits=self.fetcher.daily_cache_len() if self.fetcher else 0,
            total_latency_ms=sum(self.latencies),
            min_latency_ms=min(self.latencies) if self.latencies else 0,
            max_latency_ms=max(self.latencies) if self.latencies else 0,
            avg_latency_ms=sum(self.latencies) / len(self.latencies) if self.latencies else 0,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            requests_per_second=self.requests_made / elapsed if elapsed > 0 else 0,
            memory_used_mb=self.get_memory_usage_mb(),
            rate_limit_waits=0,  # Would need to track from fetcher
            total_wait_time_sec=0,  # Would need to track from fetcher
            errors=self.errors[:10],  # First 10 errors
        )

    def print_metrics(self, metrics: PerformanceMetrics):
        """Pretty print metrics."""
        print(f"\n{'='*60}")
        print(f"  {metrics.test_name} - RESULTS")
        print("=" * 60)
        print(f"Duration: {metrics.end_time - metrics.start_time:.1f}s")
        print(f"Symbols tested: {metrics.symbols_tested}")
        print(
            f"Requests: {metrics.requests_made} (Success: {metrics.successful_requests}, Failed: {metrics.failed_requests})"
        )
        print(
            f"Success rate: {metrics.successful_requests/metrics.requests_made*100 if metrics.requests_made else 0:.1f}%"
        )
        print(f"Request rate: {metrics.requests_per_second:.2f}/sec")
        print("\nLatency (ms):")
        print(f"  Min: {metrics.min_latency_ms:.2f}")
        print(f"  Avg: {metrics.avg_latency_ms:.2f}")
        print(f"  Max: {metrics.max_latency_ms:.2f}")
        print(f"  P50: {metrics.p50_latency_ms:.2f}")
        print(f"  P95: {metrics.p95_latency_ms:.2f}")
        print(f"  P99: {metrics.p99_latency_ms:.2f}")
        print("\nResource usage:")
        print(f"  Memory: {metrics.memory_used_mb:.1f} MB")
        print(f"  Cache entries: {metrics.cache_hits}")

        if metrics.errors:
            print(f"\nErrors encountered: {len(metrics.errors)}")
            for err in metrics.errors[:3]:
                print(f"  - {err[:100]}")


def main():
    """Run comprehensive IBKR stress tests."""
    print("=" * 60)
    print("  IBKR COMPREHENSIVE STRESS TEST SUITE")
    print("=" * 60)

    # Check environment
    print("\nConfiguration:")
    print(f"  Host: {os.getenv('SENGOKU_TWS_HOST', '127.0.0.1')}")
    print(f"  Port: {os.getenv('SENGOKU_TWS_PORT', '7496')}")
    print(f"  Client ID: {os.getenv('SENGOKU_TWS_CLIENT_ID', '107')}")

    # Create stress tester
    tester = IBKRStressTest()

    # Connect to IBKR
    if not tester.connect():
        print("\n❌ Failed to connect to IBKR. Please check TWS/Gateway is running.")
        return 1

    all_metrics = []

    try:
        # Run tests
        print("\n" + "=" * 60)
        print("  STARTING STRESS TESTS")
        print("=" * 60)

        # Test 1: Symbol scaling
        metrics = tester.test_symbol_scaling(max_symbols=100)
        tester.print_metrics(metrics)
        all_metrics.append(metrics)
        time.sleep(5)  # Cool down between tests

        # Test 2: Burst load
        metrics = tester.test_burst_load(duration_sec=30, burst_size=10)
        tester.print_metrics(metrics)
        all_metrics.append(metrics)
        time.sleep(5)

        # Test 3: Sustained load (shorter for demo)
        metrics = tester.test_sustained_load(duration_sec=60, symbols_per_request=20)
        tester.print_metrics(metrics)
        all_metrics.append(metrics)
        time.sleep(5)

        # Test 4: Market open simulation
        metrics = tester.test_market_open_simulation(symbol_count=50)
        tester.print_metrics(metrics)
        all_metrics.append(metrics)

    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        traceback.print_exc()

    # Save results
    results_file = f"ibkr_stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump([m.to_dict() for m in all_metrics], f, indent=2)

    print(f"\n\n✅ Results saved to {results_file}")

    # Summary
    print("\n" + "=" * 60)
    print("  STRESS TEST SUMMARY")
    print("=" * 60)

    total_requests = sum(m.requests_made for m in all_metrics)
    total_successful = sum(m.successful_requests for m in all_metrics)
    avg_latency = sum(m.avg_latency_ms for m in all_metrics) / len(all_metrics) if all_metrics else 0
    max_memory = max(m.memory_used_mb for m in all_metrics) if all_metrics else 0

    print(f"Total requests: {total_requests}")
    print(f"Overall success rate: {total_successful/total_requests*100 if total_requests else 0:.1f}%")
    print(f"Average latency: {avg_latency:.2f}ms")
    print(f"Peak memory usage: {max_memory:.1f} MB")

    # Performance verdict
    print("\n🎯 Performance Assessment:")
    if avg_latency < 100 and total_successful / total_requests > 0.95:
        print("  ✅ EXCELLENT - System handles load well")
    elif avg_latency < 200 and total_successful / total_requests > 0.90:
        print("  ⚠️ GOOD - Minor optimizations recommended")
    else:
        print("  ❌ NEEDS IMPROVEMENT - Consider optimizing")

    return 0


if __name__ == "__main__":
    sys.exit(main())
