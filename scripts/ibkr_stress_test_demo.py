#!/usr/bin/env python3
"""
IBKR Stress Test Demo - Runs with mock data for demonstration

This script demonstrates the stress test capabilities without requiring
a live IBKR connection. Perfect for testing and development.
"""

import json
import random
import time
from datetime import datetime

print("=" * 70)
print("  IBKR STRESS TEST DEMO (MOCK MODE)")
print("=" * 70)
print("\nThis demo simulates stress test results without requiring IBKR connection.\n")


# Simulate test execution
def run_mock_test(test_name: str, duration: float = 5.0):
    """Simulate a stress test with realistic metrics."""
    print(f"\n{'='*60}")
    print(f"  Running: {test_name}")
    print("=" * 60)

    # Progress bar simulation
    steps = 20
    for i in range(steps):
        progress = (i + 1) / steps
        bar_length = 40
        filled = int(progress * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r  Progress: [{bar}] {progress*100:.0f}%", end="", flush=True)
        time.sleep(duration / steps)

    print()  # New line after progress

    # Generate realistic mock metrics
    base_latency = random.uniform(50, 150)
    return {
        "test_name": test_name,
        "duration_sec": duration,
        "requests_made": random.randint(100, 500),
        "successful_requests": random.randint(95, 100),
        "failed_requests": random.randint(0, 5),
        "avg_latency_ms": base_latency + random.uniform(-20, 20),
        "min_latency_ms": base_latency - random.uniform(20, 40),
        "max_latency_ms": base_latency + random.uniform(50, 200),
        "p50_latency_ms": base_latency,
        "p95_latency_ms": base_latency + random.uniform(30, 80),
        "p99_latency_ms": base_latency + random.uniform(80, 150),
        "requests_per_second": random.uniform(2, 8),
        "memory_used_mb": random.uniform(150, 350),
        "cache_hits": random.randint(20, 80),
        "rate_limit_waits": random.randint(0, 10),
    }


# Run mock tests
results = []

print("\n🚀 Starting Mock Stress Tests...")

# Test 1: Symbol Scaling
test = run_mock_test("Symbol Scaling Test", 3)
results.append(test)
print(f"  ✅ Completed: {test['requests_made']} requests, {test['avg_latency_ms']:.1f}ms avg latency")

# Test 2: Burst Load
test = run_mock_test("Burst Load Test", 3)
results.append(test)
print(f"  ✅ Completed: {test['requests_per_second']:.2f} req/sec")

# Test 3: Sustained Load
test = run_mock_test("Sustained Load Test", 4)
results.append(test)
print(f"  ✅ Completed: {test['memory_used_mb']:.1f}MB memory used")

# Test 4: Market Open
test = run_mock_test("Market Open Simulation", 3)
results.append(test)
print(f"  ✅ Completed: {test['p99_latency_ms']:.1f}ms P99 latency")

# Calculate summary statistics
print("\n" + "=" * 70)
print("  STRESS TEST SUMMARY")
print("=" * 70)

total_requests = sum(r["requests_made"] for r in results)
avg_latency = sum(r["avg_latency_ms"] for r in results) / len(results)
max_memory = max(r["memory_used_mb"] for r in results)
avg_rps = sum(r["requests_per_second"] for r in results) / len(results)

print("\n📊 Aggregate Metrics:")
print(f"  Total Requests: {total_requests:,}")
print(f"  Average Latency: {avg_latency:.2f}ms")
print(f"  Average Throughput: {avg_rps:.2f} req/sec")
print(f"  Peak Memory: {max_memory:.1f} MB")

# Performance comparison
print("\n🔄 With Performance Optimizations:")
print("  JSON Processing: 5.5x faster (via orjson)")
print("  Async Operations: 1.2x faster (via uvloop)")
print(f"  Estimated improvement: ~{avg_latency/5.5:.1f}ms latency possible")

# Visual performance chart
print("\n📈 Latency Distribution (ms):")
for test_result in results:
    name = test_result["test_name"].replace(" Test", "").replace(" Simulation", "")[:15].ljust(15)
    latency = test_result["avg_latency_ms"]
    bar_length = int(latency / 5)  # Scale for display
    bar = "█" * min(bar_length, 50)
    print(f"  {name}: {bar} {latency:.1f}")

# Rate limiting status
print("\n🚦 Rate Limiting Analysis:")
total_waits = sum(r.get("rate_limit_waits", 0) for r in results)
if total_waits == 0:
    print("  ✅ No rate limiting detected - operating within IBKR limits")
elif total_waits < 10:
    print(f"  ⚠️ Minor rate limiting ({total_waits} waits) - acceptable for production")
else:
    print(f"  ❌ Significant rate limiting ({total_waits} waits) - consider reducing request rate")

# Recommendations
print("\n💡 Recommendations:")
if avg_latency < 100:
    print("  ✅ Excellent performance - ready for production")
    print("  • Current setup can handle 100+ symbols reliably")
    print("  • Consider increasing cache size for better efficiency")
elif avg_latency < 200:
    print("  ⚠️ Good performance with room for optimization")
    print("  • Enable aggressive caching (SENGOKU_TWS_DAILY_MAX_ENTRIES=200)")
    print("  • Consider batching requests during high-volume periods")
else:
    print("  ❌ Performance optimization needed")
    print("  • Reduce concurrent symbol count")
    print("  • Increase cache TTL settings")
    print("  • Review network latency to IBKR gateway")

# Save results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"ibkr_stress_demo_{timestamp}.json"
with open(output_file, "w") as f:
    json.dump(
        {
            "timestamp": timestamp,
            "mode": "mock",
            "tests": results,
            "summary": {
                "total_requests": total_requests,
                "avg_latency_ms": avg_latency,
                "avg_throughput_rps": avg_rps,
                "peak_memory_mb": max_memory,
            },
        },
        f,
        indent=2,
    )

print(f"\n💾 Results saved to: {output_file}")

print("\n" + "=" * 70)
print("  DEMO COMPLETE")
print("=" * 70)
print("\n📝 To run with live IBKR connection:")
print("  1. Set environment variables:")
print("     export SENGOKU_TWS_HOST=<your_tws_host>")
print("     export SENGOKU_TWS_PORT=7496")
print("     export SENGOKU_TWS_CLIENT_ID=107")
print("  2. Run: python scripts/ibkr_stress_test.py")
print("\n📊 To monitor live performance:")
print("  python scripts/ibkr_performance_monitor.py")
print()
