import json

import optipanel.adapters.ibkr as ibkr_mod
from optipanel.cli.main import health_main, main


class DummyFetcher:
    def __init__(self, cfg=None):
        self.cfg = cfg
        self._handshake_calls = 0
        self.last_ok = 123.45
        self.last_error = None
        self._daily_cache = {"AAPL": [1, 2], "MSFT": [3]}

    def handshake_test(self):
        self._handshake_calls += 1
        self.last_ok = 999.0
        return {"handshake": "ok", "errors": []}

    def daily_cache_len(self):
        return len(self._daily_cache)

    def last_ok_timestamp(self):
        return self.last_ok

    def last_error_message(self):
        return self.last_error

    def pacing_metrics(self):
        return {"requests_in_window": 0, "window_interval_sec": 5.0}


def test_health_main_reports_handshake(monkeypatch, capsys):
    dummy_cfg = object()
    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: dummy_cfg, raising=False)
    dummy_fetcher = DummyFetcher(dummy_cfg)
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: dummy_fetcher, raising=False)

    rc = health_main()
    assert rc == 0
    assert dummy_fetcher._handshake_calls == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert "ts" in data and "host" in data
    ibkr = data["ibkr"]
    assert ibkr["ok"] is True
    assert ibkr["daily_cache_size"] == len(dummy_fetcher._daily_cache)
    assert ibkr["pacing"]["requests_in_window"] == 0


def test_health_main_includes_last_error(monkeypatch, capsys):
    class ErrorFetcher(DummyFetcher):
        def last_error_message(self):
            return "boom"

    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: object(), raising=False)
    error_fetcher = ErrorFetcher()
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: error_fetcher, raising=False)

    rc = health_main()
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    assert data["ibkr"]["last_error"] == "boom"


def test_health_main_emits_pacing_alert(monkeypatch, capsys):
    class AlertFetcher(DummyFetcher):
        def pacing_metrics(self):
            return {
                "requests_in_window": 2,
                "window_interval_sec": 5.0,
                "last_request_latency_sec": 0.1,
                "total_requests": 10,
                "global_rate_max_requests": 40,
                "global_rate_interval_sec": 60.0,
                "global_rate_last_wait_sec": 4.0,
                "global_rate_total_wait_sec": 30.0,
                "global_rate_wait_ratio": 0.5,
            }

    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: object(), raising=False)
    fetcher = AlertFetcher()
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: fetcher, raising=False)

    rc = health_main()
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    alerts = data["ibkr"].get("pacing_alerts", [])
    assert alerts
    assert alerts[0]["severity"] in {"medium", "high"}
    assert alerts[0]["last_wait_sec"] >= 4.0


def test_health_main_threshold_overrides_disable_alerts(monkeypatch, capsys):
    class QuietFetcher(DummyFetcher):
        def pacing_metrics(self):
            return {
                "requests_in_window": 2,
                "window_interval_sec": 5.0,
                "last_request_latency_sec": 0.1,
                "total_requests": 10,
                "global_rate_max_requests": 40,
                "global_rate_interval_sec": 60.0,
                "global_rate_last_wait_sec": 4.0,
                "global_rate_total_wait_sec": 30.0,
                "global_rate_wait_ratio": 0.5,
            }

    monkeypatch.setenv("SENGOKU_TWS_PACING_LAST_WAIT_WARN", "10")
    monkeypatch.setenv("SENGOKU_TWS_PACING_LAST_WAIT_CRIT", "10")
    monkeypatch.setenv("SENGOKU_TWS_PACING_TOTAL_RATIO_WARN", "0.9")
    monkeypatch.setenv("SENGOKU_TWS_PACING_TOTAL_RATIO_CRIT", "0.9")
    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: object(), raising=False)
    fetcher = QuietFetcher()
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: fetcher, raising=False)

    rc = health_main()
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    alerts = data["ibkr"].get("pacing_alerts", [])
    assert alerts == []


def test_health_main_ping_triggers_handshake(monkeypatch, capsys):
    dummy_cfg = object()
    monkeypatch.setattr(ibkr_mod, "cfg_from_env", lambda: dummy_cfg, raising=False)
    dummy_fetcher = DummyFetcher(dummy_cfg)
    monkeypatch.setattr(ibkr_mod, "RealTwsFetcher", lambda cfg: dummy_fetcher, raising=False)

    rc = health_main(ping=True)
    assert rc == 0
    assert dummy_fetcher._handshake_calls == 1


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
