import asyncio
import types

import pytest


@pytest.mark.asyncio
async def test_app_main_smoke(monkeypatch):
    # Import lazily to avoid running on import
    from optipanel import app as app_mod

    # Patch stop_event to avoid waiting on signals
    # We intercept asyncio.Event to return a pre-set event.
    stop_event = asyncio.Event()
    stop_event.set()

    class DummyLoop:
        def add_signal_handler(self, *args, **kwargs):
            pass

    def fake_get_running_loop():
        return DummyLoop()

    # Patch pieces inside app.main
    monkeypatch.setattr(app_mod.asyncio, "Event", lambda: stop_event)
    monkeypatch.setattr(app_mod.asyncio, "get_running_loop", fake_get_running_loop)

    # Avoid real adapter/cache/scheduler work by substituting light stubs
    class DummyAdapter:
        async def get_underlying_snapshot(self, sym):
            return {"symbol": sym, "last": 100.0}

    class DummySched:
        def __init__(self, *args, **kwargs):
            self.jobs = []

        def add_job(self, name, interval, coro_fn):
            self.jobs.append((name, interval, coro_fn))

        async def stop(self):
            pass

    class DummyCache:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *_args, **_kwargs):
            pass

    class DummySettings(types.SimpleNamespace):
        cache_max_items: int = 100
        cache_default_ttl_sec: int = 60
        prime_interval_sec: int = 1
        secondary_thin_interval_sec: int = 1

    monkeypatch.setattr(app_mod, "SandboxAdapter", DummyAdapter)
    monkeypatch.setattr(app_mod, "Scheduler", DummySched)
    monkeypatch.setattr(app_mod, "TTLCache", DummyCache)
    monkeypatch.setattr(app_mod, "load_settings", lambda: DummySettings())

    # Run main and ensure it completes without error
    await app_mod.main()
