"""
Live IBKR TWS Integration Tests
Run with: IBKR_LIVE=1 pytest tests/test_ibkr_live_integration.py -v
"""

import os
import time

import pytest

# Only run if explicitly enabled
pytestmark = pytest.mark.skipif(os.getenv("IBKR_LIVE") != "1", reason="Set IBKR_LIVE=1 to run live IBKR tests")


def test_tws_connection_handshake():
    """Test basic TWS connection handshake."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),  # Default live port (set SENGOKU_TWS_PORT for paper)
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
    )

    fetcher = RealTwsFetcher(config)
    result = fetcher.handshake_test()

    assert result["handshake"] == "ok"
    assert "errors" in result
    assert result["host"] == config.host
    assert result["port"] == config.port


def test_tws_fetch_market_data():
    """Test fetching real market data for common symbols."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
    )

    fetcher = RealTwsFetcher(config)
    symbols = ["SPY", "AAPL", "MSFT"]

    features = fetcher.features_for_symbols(symbols)

    # Verify we got data for all symbols
    assert len(features) == len(symbols)

    for symbol in symbols:
        assert symbol in features
        data = features[symbol]

        # Check required fields are present
        assert "last" in data
        assert "dma20" in data
        assert "support" in data
        assert "resistance" in data
        assert "rs_strength" in data

        # Validate data types and ranges
        assert isinstance(data["last"], float)
        assert data["last"] > 0
        assert isinstance(data["dma20"], float)
        assert data["dma20"] > 0


def test_tws_cache_behavior():
    """Test that TWS caching works correctly."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
        daily_ttl_sec=60,  # Short TTL for testing
    )

    fetcher = RealTwsFetcher(config)

    # First fetch
    start = time.perf_counter()
    features1 = fetcher.features_for_symbols(["SPY"])
    time1 = time.perf_counter() - start

    # Second fetch (should be cached)
    start = time.perf_counter()
    features2 = fetcher.features_for_symbols(["SPY"])
    time2 = time.perf_counter() - start

    # Cache should make second fetch much faster
    assert time2 < time1 * 0.5  # At least 2x faster

    # Data should be identical
    assert features1["SPY"]["last"] == features2["SPY"]["last"]

    # Check cache metrics
    assert fetcher.daily_cache_len() > 0


def test_tws_pacing_and_rate_limiting():
    """Test pacing and rate limiting behavior."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
        pacing_max_requests=3,
        pacing_interval_sec=5.0,
        global_rate_max_requests=10,
        global_rate_interval_sec=60.0,
    )

    fetcher = RealTwsFetcher(config)

    # Make multiple requests to trigger pacing
    symbols_list = [
        ["SPY"],
        ["AAPL"],
        ["MSFT"],
        ["GOOGL"],
        ["TSLA"],
    ]

    for symbols in symbols_list:
        fetcher.features_for_symbols(symbols)

    # Check pacing metrics
    metrics = fetcher.pacing_metrics()
    assert metrics["total_requests"] >= 5
    assert "requests_in_window" in metrics
    assert "global_rate_wait_ratio" in metrics


def test_tws_error_handling():
    """Test error handling for invalid symbols and connection issues."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
        hist_timeout=5.0,  # Short timeout for testing
    )

    fetcher = RealTwsFetcher(config)

    # Test with invalid symbol
    features = fetcher.features_for_symbols(["INVALIDSYMBOL123"])

    # Should still return structure but with default/empty values
    assert "INVALIDSYMBOL123" in features
    data = features["INVALIDSYMBOL123"]

    # Should have structure but likely zero/default values
    assert "last" in data
    assert "dma20" in data


def test_tws_full_provider_stack():
    """Test the complete provider stack with live data."""
    from optipanel.adapters.ibkr import TwsFeaturesProvider
    from optipanel.adapters.ibkr.translator import tws_translator
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig
    from optipanel.runtime.loop import run_once_with

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
    )

    fetcher = RealTwsFetcher(config)
    provider = TwsFeaturesProvider(fetcher, tws_translator)

    # Run the full scan with live data
    result = run_once_with(provider, ["SPY", "AAPL", "MSFT"])

    # Verify scan results
    assert "scan" in result
    assert "alerts" in result
    assert "top" in result["scan"]

    # Should have some data
    assert len(result["scan"]["top"]) > 0


def test_tws_concurrent_requests():
    """Test handling of concurrent symbol requests."""
    import concurrent.futures

    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig

    config = TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "999")),
    )

    fetcher = RealTwsFetcher(config)

    # Test concurrent requests (should be serialized internally)
    def fetch_symbol(symbol):
        return fetcher.features_for_symbols([symbol])

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_symbol, symbol) for symbol in ["SPY", "AAPL", "MSFT"]]

        results = [f.result() for f in futures]

    # All should succeed
    assert len(results) == 3
    for result in results:
        assert len(result) == 1


def test_tws_secret_resolver_integration():
    """Test integration with secret resolver for credentials."""
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env

    # Test that config can be created from environment
    config = cfg_from_env()
    assert config.host is not None
    assert config.port > 0
    assert config.client_id >= 0

    # Test fetcher can be created with resolved config
    fetcher = RealTwsFetcher(config)
    assert fetcher.cfg == config
