import builtins

import pytest


def test_cli_help_runs(capsys):
    from click.testing import CliRunner
    from optipanel.cli.live_positions import live_positions

    runner = CliRunner()
    res = runner.invoke(live_positions, ["--help"])
    assert res.exit_code == 0
    assert "Live positions" in res.output or "live position" in res.output.lower()


def test_cli_runs_one_tick_without_sleep(monkeypatch, capsys):
    from click.testing import CliRunner
    from optipanel import cli as cli_pkg  # ensure package import works
    from optipanel.cli import live_positions as mod

    # Patch RealTwsFetcher and its features_for_symbols
    class DummyFetcher:
        def __init__(self, *_args, **_kwargs):
            pass

        def features_for_symbols(self, symbols):
            # Provide all fields used by compute_setups downstream
            base = {
                "last": 100.0,
                "dma20": 95.0,
                "support": 90.0,
                "resistance": 120.0,
                "rvol": 1.1,
                "rs_strength": 1.0,
                "vwap_diff": 0.0,
                "breakout_up": 100,
                "trend_long": 100,
            }
            return {s: dict(base) for s in symbols}

    monkeypatch.setattr(mod, "RealTwsFetcher", DummyFetcher)
    monkeypatch.setattr(mod, "cfg_from_env", lambda: {})

    # Avoid real sleep
    monkeypatch.setattr(mod, "time", type("T", (), {"sleep": lambda *_: None}))

    runner = CliRunner()
    res = runner.invoke(mod.live_positions, ["--symbols", "AAPL", "--ticks", "1", "--interval", "0"])
    assert res.exit_code == 0
    assert "Tick 1" in res.output
    assert "Equity:" in res.output
