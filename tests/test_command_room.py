import json
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room
from optipanel.cli.main import command_room_main

BULL = dict(last=105.0, dma20=100.0, support=101.0, resistance=106.0,
            rvol=1.6, rs_strength=0.30, vwap_diff=0.012)
BEAR = dict(last=95.0, dma20=100.0, support=96.0, resistance=100.0,
            rvol=1.5, rs_strength=-0.25, vwap_diff=-0.012)

def test_render_command_room_contains_top_and_bars():
    out = run_once({"AAA": BULL, "BBB": BEAR})
    panel = render_command_room(out, width=20, top_n=1)
    assert "COMMAND ROOM" in panel
    assert "TOP:" in panel
    assert ("AAA" in panel) or ("BBB" in panel)
    assert "dma20" in panel.lower()  # labeled battlefield bars present
    assert "advice:" in panel

def test_cli_command_room_prints_ascii(capsys):
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    rc = command_room_main(["--symbols-json", payload, "--width", "20", "--top-n", "1",
                            "--iterations", "1", "--sleep", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "COMMAND ROOM" in out and "TOP:" in out
