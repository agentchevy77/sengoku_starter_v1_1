from optipanel.adapters.ibkr import TwsFeaturesProvider
from optipanel.adapters.ibkr.fetchers_mock import MockTwsFetcher
from optipanel.adapters.ibkr.translator import translate_snapshots
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


def _kindset(alerts):
    return {(a["symbol"], a["kind"]) for a in alerts}


def test_tws_mock_path_matches_direct_decisions():
    feats = {"AAA": BULL, "BBB": BEAR}
    direct = run_once(feats)

    prov = TwsFeaturesProvider(
        fetcher=MockTwsFetcher(feats), translator=translate_snapshots  # returns raw  # raw -> features
    )
    via = run_once_with(prov, ["AAA", "BBB"])

    assert direct["scan"]["top"] == via["scan"]["top"]
    assert _kindset(direct["alerts"]) == _kindset(via["alerts"])
