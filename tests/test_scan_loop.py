from optipanel.engine.scan import run_local_scan

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


def test_scan_two_symbols_and_summary():
    symbols = {"AAA": BULL, "BBB": BEAR}
    out = run_local_scan(symbols)
    assert isinstance(out, dict)
    assert "results" in out and isinstance(out["results"], list) and len(out["results"]) == 2
    assert "advice_counts" in out and isinstance(out["advice_counts"], dict)
    ac = out["advice_counts"]
    assert ac.get("attack", 0) >= 0
    assert ac.get("defend", 0) >= 0
    assert "top" in out and isinstance(out["top"], list) and len(out["top"]) == 2
    # Results have expected shape
    for r in out["results"]:
        for k in ("symbol", "units", "setups", "score", "advice", "battlefield_bundle", "prob_chips"):
            assert k in r
        assert 0 <= r["score"] <= 100
        assert r["advice"] in ("attack", "defend", "standby")
