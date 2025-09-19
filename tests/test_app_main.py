from types import SimpleNamespace

import pytest

from optipanel import app as app_mod


class DummyScheduler:
    def __init__(self):
        self.jobs = []
        self.stopped = False
        self.registry = None
        self.cache = None

    def add_job(self, name, interval, coro_func):
        self.jobs.append((name, interval, coro_func))

    async def stop(self):
        self.stopped = True
        if self.registry is not None:
            await self.registry.shutdown()


class DummyRegistry:
    def __init__(self):
        self.shutdown_called = False

    async def shutdown(self, timeout: float = 5.0):
        self.shutdown_called = True


class DummyAdapter:
    def __init__(self):
        self.calls = []

    async def get_underlying_snapshot(self, sym):
        self.calls.append(sym)
        return {"symbol": sym, "last": 123.0}


class ImmediateEvent:
    def __init__(self):
        self.set_called = False

    async def wait(self):
        return None

    def set(self):
        self.set_called = True


class DummyLoop:
    def __init__(self):
        self.handlers = []

    def add_signal_handler(self, sig, handler):
        self.handlers.append((sig, handler))


@pytest.mark.asyncio
async def test_main_configures_scheduler_and_stops(monkeypatch):
    dummy_scheduler = DummyScheduler()
    dummy_registry = DummyRegistry()
    dummy_adapter = DummyAdapter()
    stop_event = ImmediateEvent()
    loop = DummyLoop()

    monkeypatch.setattr(
        app_mod,
        "load_settings",
        lambda: SimpleNamespace(
            cache_max_items=8,
            cache_default_ttl_sec=15,
            prime_interval_sec=1.5,
            secondary_thin_interval_sec=2.5,
        ),
    )

    def fake_scheduler(*, registry, cache):
        dummy_scheduler.registry = registry
        dummy_scheduler.cache = cache
        return dummy_scheduler

    monkeypatch.setattr(app_mod, "Scheduler", fake_scheduler)
    monkeypatch.setattr(app_mod, "AsyncResourceRegistry", lambda: dummy_registry)
    monkeypatch.setattr(app_mod, "SandboxAdapter", lambda: dummy_adapter)
    monkeypatch.setattr(app_mod.asyncio, "Event", lambda: stop_event)
    monkeypatch.setattr(app_mod.asyncio, "get_running_loop", lambda: loop)

    await app_mod.main()

    assert [name for name, _, _ in dummy_scheduler.jobs] == ["prime", "secondary-thin"]
    assert [interval for _, interval, _ in dummy_scheduler.jobs] == [1.5, 2.5]
    for _, _, coro in dummy_scheduler.jobs:
        assert callable(coro)
    assert dummy_scheduler.stopped
    assert dummy_registry.shutdown_called
    assert len(loop.handlers) == 2
    assert stop_event.set_called is False
