import json

from optipanel.cli.main import driver_main
from optipanel.runtime.driver import run_driver

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


def test_driver_under_cap_scans_every_tick():
    profile = {"soft_cap": 100, "cooldown": 2, "used_lines": 10, "scan_stride_backoff": 3}
    out = run_driver({"AAA": BULL, "BBB": BEAR}, profile, ticks=3)
    assert len(out["ticks"]) == 3
    assert out["backoff_ticks"] == 0
    assert out["scanned_count"] == 3
    assert all(t["scanned"] and not t["backoff"] for t in out["ticks"])


def test_driver_over_cap_enters_backoff_and_recovers():
    # usage: two breaches then below cap; cooldown=2 means
    # backoff continues for two ticks after usage drops
    profile = {"soft_cap": 10, "cooldown": 2, "used_lines": [20, 20, 5, 5, 5], "scan_stride_backoff": 2}
    out = run_driver({"AAA": BULL, "BBB": BEAR}, profile, ticks=5)
    ticks = out["ticks"]
    # first four ticks in backoff (two breaches + two cooldown), last tick recovers
    assert [t["backoff"] for t in ticks] == [True, True, True, True, False]
    # while in backoff we scan every 2nd tick (i%2==0): i=0,2,4 => 3 scans total
    assert out["scanned_count"] == 3
    # when we did scan, we should have run outputs with 'scan' key present
    for t in ticks:
        if t["scanned"]:
            assert t["run"] and "scan" in t["run"]


def test_driver_cli_outputs_json(capsys):

    profile = {"soft_cap": 10, "cooldown": 1, "used_lines": [20, 5, 5], "scan_stride_backoff": 2}
    payload_syms = json.dumps({"AAA": BULL, "BBB": BEAR})
    payload_profile = json.dumps(profile)
    rc = driver_main(
        ["--symbols-json", payload_syms, "--profile-json", payload_profile, "--ticks", "3", "--sleep", "0"]
    )
    assert rc == 0
    txt = capsys.readouterr().out
    data = json.loads(txt)
    assert "ticks" in data and "scanned_count" in data and "backoff_ticks" in data
