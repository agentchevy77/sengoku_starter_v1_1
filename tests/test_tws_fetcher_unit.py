import dataclasses
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

    metrics = fetcher.pacing_metrics()
    assert metrics == {
        "requests_in_window": 2,
        "window_interval_sec": base_cfg.pacing_interval_sec,
        "last_request_latency_sec": 0.123,
        "total_requests": 5,
    }
