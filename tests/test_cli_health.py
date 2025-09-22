import json

import pytest

import optipanel.adapters.ibkr as ibkr_mod
from optipanel.cli.main import health_main, main


class DummyFetcher:
    def __init__(self, cfg=None):
        self.cfg = cfg
        self._handshake_calls = 0

    def handshake_test(self):
        self._handshake_calls += 1
        return {"handshake": "ok", "errors": []}

    def daily_cache_len(self):
        return 3

    def last_ok_timestamp(self):
        return 123.45

    def last_error_message(self):
        return None

    def pacing_metrics(self):
        return {"requests_in_window": 0, "window_interval_sec": 5.0}


def test_health_main_reports_handshake(monkeypatch, capsys):
    dummy_cfg = object()
    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: dummy_cfg, raising=False)
    dummy_fetcher = DummyFetcher(dummy_cfg)
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: dummy_fetcher, raising=False)

    rc = health_main([])
    assert rc == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["handshake"] == "ok"
    assert data["daily_cache_len"] == 3
    assert pytest.approx(data["last_ok"], rel=1e-6) == 123.45
    assert data["pacing"]["requests_in_window"] == 0


def test_health_main_includes_last_error(monkeypatch, capsys):
    class ErrorFetcher(DummyFetcher):
        def last_error_message(self):
            return "boom"

    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: object(), raising=False)
    error_fetcher = ErrorFetcher()
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: error_fetcher, raising=False)

    rc = health_main([])
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    assert data["last_error"] == "boom"


def test_main_health_subcommand(monkeypatch, capsys):
    dummy_cfg = object()

    class Dummy(DummyFetcher):
        pass

    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: dummy_cfg, raising=False)
    fetcher = Dummy(dummy_cfg)
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: fetcher, raising=False)

    rc = main(["health"])
    assert rc == 0

    out = capsys.readouterr().out
    json.loads(out)  # should parse without error
