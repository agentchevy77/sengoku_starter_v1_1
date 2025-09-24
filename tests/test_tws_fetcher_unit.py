import dataclasses
import json
from collections import OrderedDict
from types import SimpleNamespace

import pytest

import optipanel.adapters.ibkr.tws_fetcher as tws_mod
from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)


@pytest.fixture
def base_cfg() -> TwsConfig:
    return TwsConfig(
        host="127.0.0.1",
        port=4001,
        client_id=7,
        ref_symbol="SPY",
        handshake_timeout=0.1,
        hist_timeout=0.1,
        daily_ttl_sec=100.0,
        intraday_ttl_sec=10.0,
        dynamic_ttl=True,
        stale_ok_sec=200.0,
        daily_max_entries=3,
        pacing_interval_sec=3.0,
        pacing_max_requests=2,
        pacing_min_delay_sec=1.0,
        pacing_error_delay_sec=0.0,
        global_rate_max_requests=5,
        global_rate_interval_sec=10.0,
    )


def test_current_ttl_switches_between_intraday_and_daily(monkeypatch, base_cfg):
    fetcher = RealTwsFetcher(base_cfg)

    monkeypatch.setattr(tws_mod.time, "localtime", lambda: SimpleNamespace(tm_hour=10))
    assert fetcher._current_ttl() == base_cfg.intraday_ttl_sec

    monkeypatch.setattr(tws_mod.time, "localtime", lambda: SimpleNamespace(tm_hour=20))
    assert fetcher._current_ttl() == base_cfg.daily_ttl_sec


def test_pace_request_enforces_min_delay(monkeypatch, base_cfg):
    fetcher = RealTwsFetcher(base_cfg)
    clock = FakeClock()
    clock.now = 10.0

    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.time, "sleep", clock.sleep)

    # First call at t=0 should not sleep
    fetcher._pace_request()
    assert clock.sleeps == []
    assert pytest.approx(fetcher._last_request_ts, abs=1e-6) == 10.0

    # Second call shortly after should trigger min-delay sleep (advance to 0.2 before call)
    clock.advance(0.2)
    fetcher._pace_request()
    assert clock.sleeps[-1] == pytest.approx(0.8, rel=1e-2)
    assert fetcher._fresh_requests == 2


def test_pace_request_applies_window_limit(monkeypatch, base_cfg):
    cfg = dataclasses.replace(base_cfg, pacing_min_delay_sec=0.0)
    fetcher = RealTwsFetcher(cfg)
    clock = FakeClock()
    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.time, "sleep", clock.sleep)

    fetcher._pace_request()  # t=0
    clock.advance(0.5)
    fetcher._pace_request()  # t=0.5, second request
    clock.advance(0.5)
    fetcher._pace_request()  # should sleep to respect interval window

    assert clock.sleeps[-1] == pytest.approx(3.0 - 1.0 + 0.01, rel=1e-2)
    # Request window should not exceed pacing_max_requests
    assert len(fetcher._request_window) <= base_cfg.pacing_max_requests


def test_pace_request_uses_global_rate_limiter(monkeypatch, base_cfg):
    cfg = dataclasses.replace(
        base_cfg,
        pacing_min_delay_sec=0.0,
        pacing_interval_sec=0.0,
        pacing_max_requests=0,
    )
    fetcher = RealTwsFetcher(cfg)

    class DummyLimiter:
        def __init__(self, wait: float) -> None:
            self.enabled = True
            self.wait = wait
            self.calls = 0

        def acquire(self, tokens: float = 1.0) -> float:
            self.calls += 1
            return self.wait

    dummy = DummyLimiter(wait=0.5)
    fetcher._global_rate_limiter = dummy
    fetcher._rate_wait_total = 1.0
    fetcher._rate_wait_last = 0.0

    clock = FakeClock()
    clock.now = 0.0
    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.time, "sleep", clock.sleep)

    fetcher._pace_request()

    assert dummy.calls == 1
    assert fetcher._rate_wait_last == pytest.approx(0.5)
    assert fetcher._rate_wait_total == pytest.approx(1.5)


def test_get_cached_refreshes_and_respects_ttl(monkeypatch):
    cfg = TwsConfig(dynamic_ttl=False, daily_ttl_sec=10.0)
    fetcher = RealTwsFetcher(cfg)
    bars = [("2024-01-01", 1.0, 1.0, 1.0, 1.0, 100)]
    fetcher._daily_cache = OrderedDict({"AAPL": (0.0, bars)})

    now = 5.0
    result = fetcher._get_cached("AAPL", now, allow_stale=False)
    assert result == bars
    ts, _ = fetcher._daily_cache["AAPL"]
    assert ts == now

    # Exceed TTL without allow_stale should return None
    result = fetcher._get_cached("AAPL", now + 11.0, allow_stale=False)
    assert result is None

    # allow_stale should serve the data while under stale_ok_sec
    cfg = TwsConfig(dynamic_ttl=False, daily_ttl_sec=1.0, stale_ok_sec=20.0)
    fetcher = RealTwsFetcher(cfg)
    fetcher._daily_cache = OrderedDict({"AAPL": (0.0, bars)})
    assert fetcher._get_cached("AAPL", 5.0, allow_stale=True) == bars


def test_prune_daily_cache_drops_lru():
    cfg = TwsConfig(daily_max_entries=2)
    fetcher = RealTwsFetcher(cfg)
    fetcher._daily_cache = OrderedDict(
        {
            "A": (1.0, [1]),
            "B": (2.0, [2]),
            "C": (3.0, [3]),
        }
    )

    fetcher._prune_daily_cache()
    assert list(fetcher._daily_cache.keys()) == ["B", "C"]


def test_pacing_metrics_reports_window(monkeypatch, base_cfg):
    fetcher = RealTwsFetcher(base_cfg)
    fetcher._request_window.extend([1.0, 2.0])
    fetcher._last_latency = 0.123
    fetcher._fresh_requests = 5
    fetcher._rate_wait_last = 0.5
    fetcher._rate_wait_total = 2.0
    fetcher._rate_wait_events.clear()

    metrics = fetcher.pacing_metrics()
    assert metrics == {
        "requests_in_window": 2,
        "window_interval_sec": base_cfg.pacing_interval_sec,
        "last_request_latency_sec": 0.123,
        "total_requests": 5,
        "global_rate_max_requests": base_cfg.global_rate_max_requests,
        "global_rate_interval_sec": base_cfg.global_rate_interval_sec,
        "global_rate_last_wait_sec": 0.5,
        "global_rate_total_wait_sec": 2.0,
        "global_rate_wait_ratio": pytest.approx(2.0 / base_cfg.global_rate_interval_sec),
    }


def test_connect_success_sets_last_ok(monkeypatch, base_cfg):
    clock = FakeClock()
    clock.now = 100.0
    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.threading, "Thread", DummyThread)

    created = {}

    def hist_factory():
        app = DummyApp(True)
        created["app"] = app
        return app

    monkeypatch.setattr(tws_mod, "_HistApp", hist_factory)

    fetcher = RealTwsFetcher(base_cfg)
    app = fetcher._connect()

    assert app is created["app"]
    assert app.connect_args == (base_cfg.host, base_cfg.port, base_cfg.client_id)
    assert app.run_called is True
    assert fetcher._last_ok == pytest.approx(100.0, abs=1e-6)
    assert fetcher._last_error is None
    assert app.ready.wait_calls == [base_cfg.handshake_timeout]


def test_handshake_test_disconnects(monkeypatch, base_cfg):
    clock = FakeClock()
    clock.now = 42.0
    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.threading, "Thread", DummyThread)

    last = {}

    def factory():
        app = DummyApp(True)
        last["app"] = app
        return app

    monkeypatch.setattr(tws_mod, "_HistApp", factory)

    fetcher = RealTwsFetcher(base_cfg)
    result = fetcher.handshake_test()

    assert last["app"].disconnect_called is True
    assert result == {
        "host": base_cfg.host,
        "port": base_cfg.port,
        "client_id": base_cfg.client_id,
        "handshake": "ok",
        "errors": [],
        "last_ok": pytest.approx(42.0, abs=1e-6),
    }


def test_connect_timeout_raises(monkeypatch, base_cfg):
    clock = FakeClock()
    clock.now = 5.0
    monkeypatch.setattr(tws_mod.time, "time", clock.time)
    monkeypatch.setattr(tws_mod.threading, "Thread", DummyThread)

    container = {}

    def factory():
        app = DummyApp(False)
        container["app"] = app
        return app

    monkeypatch.setattr(tws_mod, "_HistApp", factory)

    fetcher = RealTwsFetcher(base_cfg)

    with pytest.raises(TimeoutError):
        fetcher._connect()

    assert container["app"].disconnect_called is True
    assert fetcher._last_ok == 0.0
    assert "handshake timeout" in fetcher._last_error


def test_hist_app_collects_bars_even_with_late_updates():
    app = tws_mod._HistApp()

    bar1 = SimpleNamespace(date="20240101", open=1.0, high=1.5, low=0.9, close=1.4, volume=100)
    bar2 = SimpleNamespace(date="20240102", open=1.4, high=1.6, low=1.2, close=1.5, volume=120)

    app.historicalData(10, bar1)
    app.historicalDataEnd(10, "", "")
    app.historicalData(10, bar2)  # simulate late bar after completion

    bars = app.take_bars(10)
    assert bars == [
        ("20240101", 1.0, 1.5, 0.9, 1.4, 100),
        ("20240102", 1.4, 1.6, 1.2, 1.5, 120),
    ]

    app.release(10)
    assert app._bars.get(10) is None
    assert app._results.get(10) is None


class DummyReady:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.wait_calls: list[float] = []
        self.set_called = False

    def wait(self, timeout: float) -> bool:
        self.wait_calls.append(timeout)
        return self.result

    def set(self) -> None:
        self.set_called = True


class DummyApp:
    def __init__(self, ready_result: bool = True) -> None:
        self.ready = DummyReady(ready_result)
        self.errors: list[tuple[int, str]] = []
        self.connect_args: tuple[str, int, int] | None = None
        self.run_called = False
        self.disconnect_called = False

    def connect(self, host: str, port: int, clientId: int) -> None:  # noqa: N803 (match ibapi signature)
        self.connect_args = (host, port, clientId)

    def run(self) -> None:
        self.run_called = True

    def disconnect(self) -> None:
        self.disconnect_called = True


class DummyThread:
    def __init__(self, target, name: str, daemon: bool):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self) -> None:
        self.started = True
        self.target()


def test_cfg_from_env_uses_secret_resolver(tmp_path, monkeypatch):
    secrets_path = tmp_path / "secrets.json"
    secrets_path.write_text(json.dumps({"SENGOKU_TWS_HOST": "192.168.0.1", "SENGOKU_TWS_PORT": 4100}))

    monkeypatch.setenv("SENGOKU_SECRETS_SOURCE", "file")
    monkeypatch.setenv("SENGOKU_SECRETS_FILE", str(secrets_path))

    cfg = tws_mod.cfg_from_env()
    assert cfg.host == "192.168.0.1"
    assert cfg.port == 4100
