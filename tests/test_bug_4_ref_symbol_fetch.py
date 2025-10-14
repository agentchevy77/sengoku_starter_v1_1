from __future__ import annotations

from decimal import Decimal
from typing import Any

from optipanel.adapters.ibkr.provider import TwsFeaturesProvider
from optipanel.adapters.ibkr.translator import tws_translator
from optipanel.indicators.intra import assemble_features_from_bars


def _make_bar_series(base: float, step: float) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    price = base
    for idx in range(1, 25):
        high = price + 0.6
        low = price - 0.4
        bars.append({"date": f"2024-01-{idx:02d}", "o": price - 0.2, "h": high, "l": low, "c": price, "v": 1_000 + idx})
        price += step
    return bars


def _build_provider(fetch_calls: list[list[str]], bars_map: dict[str, list[dict[str, Any]]]) -> TwsFeaturesProvider:
    def fetcher(symbols: list[str]) -> dict[str, dict[str, Any]]:
        fetch_calls.append(list(symbols))
        return {sym: {"bars": list(bars_map.get(sym, []))} for sym in symbols}

    return TwsFeaturesProvider(fetcher=fetcher, translator=tws_translator, benchmark_symbol="SPY")


def test_provider_adds_benchmark_when_missing() -> None:
    bars_spy = _make_bar_series(100.0, 0.5)
    bars_aapl = _make_bar_series(150.0, 1.0)
    fetch_calls: list[list[str]] = []

    provider = _build_provider(fetch_calls, {"SPY": bars_spy, "AAPL": bars_aapl})
    features = provider.features_for_symbols(["AAPL"])

    # Fetcher should have been called once with both the requested symbol and benchmark.
    assert len(fetch_calls) == 1
    assert set(fetch_calls[0]) == {"AAPL", "SPY"}

    # Provider only returns data for requested symbols.
    assert set(features.keys()) == {"AAPL"}
    expected = assemble_features_from_bars(bars_aapl, benchmark_bars=bars_spy)
    assert features["AAPL"] == expected


def test_provider_does_not_duplicate_benchmark_request() -> None:
    bars_spy = _make_bar_series(100.0, 0.5)
    bars_aapl = _make_bar_series(150.0, 1.0)
    fetch_calls: list[list[str]] = []

    provider = _build_provider(fetch_calls, {"SPY": bars_spy, "AAPL": bars_aapl})
    provider.features_for_symbols(["SPY", "AAPL"])

    assert len(fetch_calls) == 1
    assert set(fetch_calls[0]) == {"AAPL", "SPY"}


def test_provider_rs_strength_uses_benchmark() -> None:
    bars_spy = _make_bar_series(90.0, 0.2)
    bars_aapl = _make_bar_series(120.0, 1.5)
    fetch_calls: list[list[str]] = []

    provider = _build_provider(fetch_calls, {"SPY": bars_spy, "AAPL": bars_aapl})
    result = provider.features_for_symbols(["AAPL"])

    expected = assemble_features_from_bars(bars_aapl, benchmark_bars=bars_spy)
    assert result["AAPL"]["rs_strength"] == expected["rs_strength"]
    assert isinstance(result["AAPL"]["rs_strength"], Decimal)


def test_provider_handles_missing_benchmark_gracefully() -> None:
    bars_aapl = _make_bar_series(120.0, 1.0)
    fetch_calls: list[list[str]] = []

    provider = _build_provider(fetch_calls, {"AAPL": bars_aapl})
    result = provider.features_for_symbols(["AAPL"])

    assert len(fetch_calls) == 1
    assert set(fetch_calls[0]) == {"AAPL", "SPY"}
    # Without benchmark bars the indicator defaults to zeros.
    expected = assemble_features_from_bars(bars_aapl, benchmark_bars=None)
    assert result["AAPL"]["rs_strength"] == expected["rs_strength"]
