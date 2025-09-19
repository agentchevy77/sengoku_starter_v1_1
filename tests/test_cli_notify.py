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


def test_cli_notify_outputs_events(capsys):
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    rc = notify_main(["--symbols-json", payload, "--iterations", "2"])
    assert rc == 0
    txt = capsys.readouterr().out
    data = json.loads(txt)
    assert "events" in data and isinstance(data["events"], list) and len(data["events"]) >= 1
