import json
from optipanel.runtime.loop import run_once
from optipanel.cli.main import loop_main

BULL = dict(last=105.0, dma20=100.0, support=101.0, resistance=106.0,
            rvol=1.6, rs_strength=0.30, vwap_diff=0.012)
BEAR = dict(last=95.0, dma20=100.0, support=96.0, resistance=100.0,
            rvol=1.5, rs_strength=-0.25, vwap_diff=-0.012)

def test_run_once_has_scan_and_alerts():
    out = run_once({"AAA": BULL, "BBB": BEAR})
    assert "scan" in out and "alerts" in out
    assert isinstance(out["scan"], dict)
    assert isinstance(out["scan"]["results"], list)
    assert isinstance(out["alerts"], list)
    # sanity: both symbols represented somewhere in output
    syms_scan = {r["symbol"] for r in out["scan"]["results"]}
    syms_alert = {a["symbol"] for a in out["alerts"]}
    assert {"AAA","BBB"} & syms_scan
    assert {"AAA","BBB"} <= (syms_scan | syms_alert)

def test_loop_main_json(capsys):
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    rc = loop_main(["--symbols-json", payload, "--iterations", "2", "--sleep", "0"])
    assert rc == 0
    text = capsys.readouterr().out
    data = json.loads(text)
    assert data["iterations"] == 2
    assert "runs" in data and len(data["runs"]) == 2
    # each run has scan+alerts
    for r in data["runs"]:
        assert "scan" in r and "alerts" in r
        assert isinstance(r["scan"]["results"], list)
