from __future__ import annotations

import json

from optipanel.cli.main import alerts_main

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}


def _invoke(args: list[str], capsys, monkeypatch) -> list[dict[str, object]]:
    monkeypatch.delenv("SENGOKU_ALERTS_INCLUDE_SUPPLY", raising=False)
    rc = alerts_main(args)
    assert rc == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert isinstance(data, list) and data, "alerts output should be a non-empty list"
    return data


def test_cli_alerts_default_skips_supply(capsys, monkeypatch):
    payload = json.dumps({"AAA": BULL})
    alerts = _invoke(["--symbols-json", payload], capsys, monkeypatch)
    first = alerts[0]
    assert "sustainment" in first
    assert "supply" not in first


def test_cli_alerts_include_supply_flag(capsys, monkeypatch):
    payload = json.dumps({"AAA": BULL})
    alerts = _invoke(["--symbols-json", payload, "--include-supply"], capsys, monkeypatch)
    assert any(alert.get("supply") for alert in alerts), "expected supply factors when flag enabled"
