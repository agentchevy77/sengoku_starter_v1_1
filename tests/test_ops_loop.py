import importlib

from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.ops import ops_loop

ops_module = importlib.import_module("optipanel.ops.ops_loop")


class DummyProvider:
    def __init__(self):
        self.calls = []

    def features_for_symbols(self, symbols):
        self.calls.append(tuple(symbols))
        return {sym: {"last": 100.0, "dma20": 99.0, "support": 95.0, "resistance": 105.0} for sym in symbols}


def test_ops_loop_respects_backoff(monkeypatch):
    provider = DummyProvider()
    profile = {
        "watchlists": {"prime": ["AAPL"], "secondary": ["MSFT"]},
        "budgets": {
            "prime": {"used_lines": [5, 25, 5, 5, 5], "soft_cap": 20, "cooldown": 2, "scan_stride": 1},
            "secondary": {"scan_stride": 2},
        },
    }

    captured = []

    def fake_run_watchlist_once(_provider, symbols, *, width, top_n):
        captured.append((tuple(symbols), width, top_n))
        return {"panel": "panel", "run": {}}

    monkeypatch.setattr(ops_module, "run_watchlist_once", fake_run_watchlist_once)

    result = ops_loop(provider, profile, ticks=5, sleep=0, width=24, top_n=2)

    prime_ticks = [entry["tick"] for entry in result["runs"] if entry["list"] == "prime"]
    secondary_ticks = [entry["tick"] for entry in result["runs"] if entry["list"] == "secondary"]

    assert prime_ticks == [0, 4]
    assert secondary_ticks == [0, 2, 4]
    assert captured[0] == (("AAPL",), 24, 2)
    assert captured[1] == (("MSFT",), 24, 2)


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


def test_ops_runs_prime_and_secondary_without_backoff():
    profile = {
        "watchlists": {"prime": ["AAA", "BBB"], "secondary": ["BBB"]},
        "budgets": {
            "prime": {"soft_cap": 20, "cooldown": 1, "used_lines": [1, 1, 1], "scan_stride": 1},
            "secondary": {"scan_stride": 2},
        },
        "ui": {"width": 24, "top_n": 1},
    }
    provider = MockFeaturesProvider({"AAA": BULL, "BBB": BEAR})
    out = ops_loop(provider, profile, ticks=3, sleep=0, width=24, top_n=1)
    assert out["ticks"] == 3
    assert any("COMMAND ROOM" in r["panel"].upper() for r in out["runs"])
    assert len(out["runs"]) >= 2
