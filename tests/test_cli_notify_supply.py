import json

from optipanel.cli.main import notify_main

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


def _run_notify(args, capsys):
    rc = notify_main(args)
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, dict)
    events = data.get("events") or data.get("alerts") or []
    assert events, "Expected events in notify output"
    return events


def test_notify_sustainment_always_present(monkeypatch, capsys):
    monkeypatch.delenv("SENGOKU_NOTIFY_INCLUDE_SUPPLY", raising=False)
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    events = _run_notify(["--symbols-json", payload], capsys)
    for event in events:
        assert "sustainment" in event
        sustain = event["sustainment"]
        assert "sustainability" in sustain and "fakeout_risk" in sustain


def test_notify_supply_opt_in(monkeypatch, capsys):
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    monkeypatch.setenv("SENGOKU_NOTIFY_INCLUDE_SUPPLY", "1")
    events = _run_notify(["--symbols-json", payload], capsys)
    assert any("supply" in event for event in events), "Expected supply factors when flag/env enabled"
