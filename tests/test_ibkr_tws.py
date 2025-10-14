from optipanel.adapters.ibkr import TwsFeaturesProvider
from optipanel.runtime.loop import run_once, run_once_with

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}
BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 1.5,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
}


def test_tws_provider_matches_direct_features_identity_translation():
    def fake_fetcher(symbols):
        table = {"AAA": BULL, "BBB": BEAR, "SPY": BULL}
        return {s: table[s] for s in symbols if s in table}

    def identity_translator(raw, **kwargs):
        return {k: dict(v) for k, v in raw.items()}

    prov = TwsFeaturesProvider(fake_fetcher, identity_translator)

    direct = run_once({"AAA": BULL, "BBB": BEAR})
    via = run_once_with(prov, ["AAA", "BBB"])

    assert direct["scan"]["top"] == via["scan"]["top"]
    # compare alert kinds per symbol
    kindset_direct = {(a["symbol"], a["kind"]) for a in direct["alerts"]}
    kindset_via = {(a["symbol"], a["kind"]) for a in via["alerts"]}
    assert kindset_direct == kindset_via


def test_tws_provider_sanitizes_missing_and_bad_values():
    def fake_fetcher(symbols):
        return {"ZZZ": {"last": "bad", "dma20": None}}  # missing most keys, bad types

    def identity_translator(raw, **kwargs):
        return raw

    prov = TwsFeaturesProvider(fake_fetcher, identity_translator)
    out = prov.features_for_symbols(["ZZZ"])
    f = out["ZZZ"]
    assert f == {"last": "bad", "dma20": None}
