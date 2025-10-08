from __future__ import annotations

from optipanel.cli.main import notify_cmd

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}


def test_notify_cmd_without_supply():
    symbols = {"AAA": BULL}
    out = notify_cmd(symbols, iterations=1, include_supply=False)
    assert "events" in out
    assert all("supply" not in event for event in out["events"])
    assert all("sustainment" in event for event in out["events"])


def test_notify_cmd_with_supply():
    symbols = {"AAA": BULL}
    out = notify_cmd(symbols, iterations=1, include_supply=True)
    assert any(event.get("supply") for event in out["events"])


def test_supply_toggle_does_not_leak_between_runs():
    symbols = {"AAA": BULL}

    with_supply = notify_cmd(symbols, iterations=1, include_supply=True)
    without_supply = notify_cmd(symbols, iterations=1, include_supply=False)

    assert any("supply" in event for event in with_supply["events"])
    assert all("supply" not in event for event in without_supply["events"])
