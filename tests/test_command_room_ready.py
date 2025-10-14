from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room

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
FEED = {"AAA": BULL, "BBB": BEAR}


def test_command_room_contains_ready_line():
    out = run_once(FEED)
    panel = render_command_room(out, width=24, top_n=1).lower()
    assert "ready" in panel
    assert "attack=" in panel
