#!/usr/bin/env python3
"""
Quick IBKR connection test using configured parameters.
"""
import os
import sys

# Use actual configured parameters
print("Testing IBKR connection with configured parameters:")
print(f"  Host: {os.getenv('SENGOKU_TWS_HOST', '127.0.0.1')}")
print(f"  Port: {os.getenv('SENGOKU_TWS_PORT', '7496')}")
print(f"  Client ID: {os.getenv('SENGOKU_TWS_CLIENT_ID', '107')}")
print()

try:
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env

    print("Creating fetcher with environment config...")
    config = cfg_from_env()
    fetcher = RealTwsFetcher(config)

    print("Testing handshake...")
    result = fetcher.handshake_test()

    if result["handshake"] == "ok":
        print("✓ Handshake successful!")
        print(f"  Last OK: {result.get('last_ok', 'N/A')}")
        print(f"  Errors: {result.get('errors', [])}")

        print("\nFetching market data for SPY...")
        features = fetcher.features_for_symbols(["SPY"])

        if "SPY" in features:
            spy_data = features["SPY"]
            print("✓ SPY data received!")
            print(f"  Last: ${spy_data.get('last', 0):.2f}")
            print(f"  DMA20: ${spy_data.get('dma20', 0):.2f}")
            print(f"  Support: ${spy_data.get('support', 0):.2f}")
            print(f"  Resistance: ${spy_data.get('resistance', 0):.2f}")
        else:
            print("✗ No SPY data received")

        print("\nCache status:")
        print(f"  Cached symbols: {fetcher.daily_cache_len()}")

        print("\nPacing metrics:")
        metrics = fetcher.pacing_metrics()
        print(f"  Total requests: {metrics.get('total_requests', 0)}")
        print(f"  Requests in window: {metrics.get('requests_in_window', 0)}")

    else:
        print("✗ Handshake failed")
        print(f"  Result: {result}")

except TimeoutError as e:
    print(f"✗ Connection timeout: {e}")
    print("  Check that TWS/IB Gateway is running and API connections are enabled")
    sys.exit(1)

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n✓ All tests completed successfully!")
