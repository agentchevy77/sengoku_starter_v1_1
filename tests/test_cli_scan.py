import json

from optipanel.cli.main import scan_main

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


def test_scan_main_produces_json(capsys):
    symbols = {"AAA": BULL, "BBB": BEAR}
    rc = scan_main(["--symbols-json", json.dumps(symbols)])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "results" in data and "top" in data and "advice_counts" in data
    assert sorted(data["top"]) == ["AAA", "BBB"]
