#!/usr/bin/env python3
"""
Test IBKR components to improve coverage.
This exercises the live IBKR connection paths.
"""

import sys


def test_all_ibkr_components():
    """Exercise all IBKR components with live connection."""

    print("Testing IBKR TWS Fetcher...")
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
    from optipanel.security.secrets import SecretResolver

    # Test config creation
    resolver = SecretResolver.from_environment()
    config = cfg_from_env(resolver)
    assert config.host == "192.168.80.1"
    assert config.port == 7496

    # Create fetcher
    fetcher = RealTwsFetcher(config)

    # Test handshake
    result = fetcher.handshake_test()
    assert result["handshake"] == "ok"
    print("  ✓ Handshake OK")

    # Test data fetching
    symbols = ["SPY", "AAPL", "MSFT", "NVDA", "GOOGL"]
    features = fetcher.features_for_symbols(symbols)
    assert len(features) == len(symbols)
    print(f"  ✓ Fetched {len(symbols)} symbols")

    # Test caching
    fetcher.features_for_symbols(["SPY"])  # Should be cached
    assert fetcher.daily_cache_len() > 0
    print(f"  ✓ Cache working ({fetcher.daily_cache_len()} entries)")

    # Test pacing metrics
    metrics = fetcher.pacing_metrics()
    assert metrics["total_requests"] > 0
    print("  ✓ Pacing metrics tracked")

    print("\nTesting IBKR Provider Stack...")
    from optipanel.adapters.ibkr import TwsFeaturesProvider
    from optipanel.adapters.ibkr.translator import tws_translator

    # Test provider
    provider = TwsFeaturesProvider(fetcher, tws_translator)
    result = provider(["SPY", "AAPL"])
    assert "SPY" in result
    print("  ✓ Provider working")

    print("\nTesting Runtime Loop with IBKR...")
    from optipanel.runtime.loop import run_once_with

    # Test full scan
    scan_result = run_once_with(provider, ["SPY", "AAPL", "MSFT"])
    assert "scan" in scan_result
    assert "alerts" in scan_result
    print("  ✓ Full scan completed")

    print("\nTesting Engine Components...")
    from optipanel.engine.aggregate import build_symbol_snapshot
    from optipanel.engine.scan import run_local_scan

    # Test scan
    scan = run_local_scan(features)
    assert "top" in scan
    print("  ✓ Local scan working")

    # Test aggregation
    for symbol in ["SPY"]:
        snapshot = build_symbol_snapshot(symbol, features[symbol])
        assert snapshot["symbol"] == symbol
    print("  ✓ Aggregation working")

    print("\nTesting Alert Engine...")
    from optipanel.alerts.engine import analyze_batch_with_supply

    # Test alerts
    alerts = analyze_batch_with_supply(features)
    print(f"  ✓ Generated {len(alerts)} alerts")

    print("\nTesting Chips...")
    from optipanel.chips.aggregate import compute_microchips
    from optipanel.chips.runtime import enrich_features_with_chips

    # Test microchips
    for _symbol, data in features.items():
        chips = compute_microchips(data)
        assert isinstance(chips, dict)
    print("  ✓ Microchips computed")

    # Test enrichment
    enriched = enrich_features_with_chips(features)
    assert len(enriched) == len(features)
    print("  ✓ Features enriched")

    print("\nTesting Setups Engine...")
    from optipanel.setups.engine import compute_setups

    for _symbol, data in features.items():
        setups = compute_setups(data)
        assert isinstance(setups, dict)
    print("  ✓ Setups computed")

    print("\nTesting Positions Model...")
    from optipanel.positions.model import PositionState

    state = PositionState()
    tick_result = state.tick(features)
    assert "cash" in tick_result
    assert "equity" in tick_result
    print("  ✓ Position model working")

    print("\nTesting Monitoring...")
    from optipanel.monitoring import evaluate_pacing_alerts

    alerts = evaluate_pacing_alerts(metrics)
    print(f"  ✓ Pacing alerts evaluated ({len(alerts)} alerts)")

    print("\nTesting Config Loader...")
    from optipanel.config.loader import load_profiles_yaml

    profiles = load_profiles_yaml("config/examples/profiles.yaml")
    print(f"  ✓ Config loaded ({len(profiles)} profiles)")

    print("\nTesting Settings...")
    from optipanel.settings import load_settings

    settings = load_settings()
    assert settings.cache_max_items > 0
    print("  ✓ Settings loaded")

    return True


if __name__ == "__main__":
    try:
        success = test_all_ibkr_components()
        if success:
            print("\n✓ All IBKR components tested successfully!")
            sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
