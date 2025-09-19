from click.testing import CliRunner

from optipanel.cli import live_positions as cli_mod


def _features_for(symbols):
    return {
        sym: {
            "last": 100.0,
            "dma20": 95.0,
            "support": 90.0,
            "resistance": 110.0,
            "rvol": 1.2,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }
        for sym in symbols
    }


def test_live_positions_cli_runs_with_stubbed_fetcher(monkeypatch):
    sleep_calls = []

    class DummyFetcher:
        instances = []

        def __init__(self, cfg):
            self.cfg = cfg
            self.calls = []
            DummyFetcher.instances.append(self)

        def features_for_symbols(self, symbols):
            self.calls.append(tuple(symbols))
            return _features_for(symbols)

    monkeypatch.setattr(cli_mod, "RealTwsFetcher", DummyFetcher)
    monkeypatch.setattr(cli_mod, "cfg_from_env", lambda: object())
    monkeypatch.setattr(cli_mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    runner = CliRunner()
    result = runner.invoke(
        cli_mod.live_positions,
        [
            "--capital",
            "100000",
            "--risk",
            "0.02",
            "--symbols",
            "AAPL,MSFT",
            "--ticks",
            "2",
            "--interval",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "Tick 1" in result.output
    assert "FINAL" in result.output
    assert sleep_calls == [0]
    fetcher = DummyFetcher.instances[0]
    assert len(fetcher.calls) == 2
    assert fetcher.calls[0] == ("AAPL", "MSFT")
