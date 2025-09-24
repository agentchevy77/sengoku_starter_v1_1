from optipanel.adapters.ibkr.translator import translate_snapshots, tws_translator


def test_tws_translator_alias() -> None:
    raw = {
        "SPY": {
            "last": "123.4",
            "dma20": None,
            "support": 120,
            "resistance": 130,
            "rvol": "1.2",
            "rs_strength": "0.6",
            "vwap_diff": "-0.4",
        }
    }

    expected = translate_snapshots(raw)
    assert expected == tws_translator(raw)
    assert expected["SPY"]["dma20"] == 0.0  # coerced default


def test_tws_features_provider_callable(monkeypatch):
    from optipanel.adapters.ibkr.provider import TwsFeaturesProvider

    symbols = ["SPY"]

    def fake_fetcher(requested):
        assert requested == symbols
        return {"SPY": {"last": "100"}}

    provider = TwsFeaturesProvider(fake_fetcher, tws_translator)
    via_method = provider.features_for_symbols(symbols)
    via_call = provider(symbols)
    assert via_method == via_call
    assert via_call["SPY"]["last"] == 100.0
