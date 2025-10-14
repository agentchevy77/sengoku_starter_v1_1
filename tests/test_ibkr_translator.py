from decimal import Decimal

from optipanel.adapters.ibkr.provider import TwsFeaturesProvider
from optipanel.adapters.ibkr.translator import translate_snapshots, tws_translator
from optipanel.indicators.intra import assemble_features_from_bars


def _sample_bars(base: float) -> list[dict[str, float]]:
    return [
        {"o": base - 1, "h": base + 1, "l": base - 2, "c": base - 0.5, "v": 1_000},
        {"o": base - 0.5, "h": base + 1.2, "l": base - 1, "c": base, "v": 1_100},
        {"o": base, "h": base + 1.5, "l": base - 0.4, "c": base + 0.75, "v": 1_200},
    ]


def test_tws_translator_generates_decimal_features_with_benchmark() -> None:
    bars_sym = _sample_bars(50.0)
    bars_bench = _sample_bars(48.0)
    raw = {"AAA": {"bars": bars_sym}, "SPY": {"bars": bars_bench}}

    out = tws_translator(raw, benchmark_symbol="SPY", window=3)
    expected = assemble_features_from_bars(bars_sym, benchmark_bars=bars_bench, window=3)

    assert "AAA" in out
    assert "SPY" not in out  # benchmark symbol excluded
    assert out["AAA"] == expected
    assert all(isinstance(val, Decimal) for val in out["AAA"].values())
    assert out["AAA"]["rs_strength"] != Decimal("0")


def test_tws_translator_handles_missing_bars() -> None:
    raw = {"AAA": {"bars": []}, "SPY": {"bars": []}}
    out = tws_translator(raw, benchmark_symbol="SPY")
    assert out == {"AAA": {}}


def test_translate_snapshots_pass_through_warns(monkeypatch, caplog) -> None:
    caplog.set_level("WARNING")
    raw = {"AAA": {"last": Decimal("10.0"), "dma20": Decimal("9.5")}}
    out = translate_snapshots(raw, benchmark_symbol="SPY")
    assert out == raw
    assert any("LEGACY translate_snapshots" in rec.message for rec in caplog.records)


def test_tws_features_provider_callable_includes_benchmark(monkeypatch) -> None:
    bars_sym = _sample_bars(25.0)
    bars_bench = _sample_bars(24.5)
    symbols = ["AAA"]

    def fake_fetcher(requested):
        assert set(requested) == {"AAA", "SPY"}
        return {"AAA": {"bars": bars_sym}, "SPY": {"bars": bars_bench}}

    provider = TwsFeaturesProvider(fake_fetcher, tws_translator, benchmark_symbol="SPY")

    via_method = provider.features_for_symbols(symbols)
    via_call = provider(symbols)
    expected = assemble_features_from_bars(bars_sym, benchmark_bars=bars_bench)

    assert via_method == via_call
    assert via_call["AAA"] == expected
