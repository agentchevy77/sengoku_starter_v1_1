import asyncio
from types import SimpleNamespace

import pytest

from optipanel.services.leakguard import AsyncResourceRegistry, LeakSentinel, PeriodicTask


async def dummy_work():
    await asyncio.sleep(0.001)


async def run_cycles():
    reg = AsyncResourceRegistry()
    task = PeriodicTask(dummy_work, 0.001, reg, name="dummy")
    task.start()
    await asyncio.sleep(0.05)
    await task.stop()
    await reg.shutdown()


def test_memory_leak_guard():
    with LeakSentinel(label="cycles", budget_bytes=1_000_000):
        asyncio.run(run_cycles())


@pytest.mark.asyncio
async def test_registry_shutdown_handles_closers():
    reg = AsyncResourceRegistry()

    loop = asyncio.get_running_loop()
    pending = asyncio.Event()
    task = loop.create_task(pending.wait())
    reg.track_task(task)

    markers = {"aclose": 0, "async_close": 0, "async_shutdown": 0, "sync_close": 0, "sync_shutdown": 0}

    class HashableNamespace(SimpleNamespace):
        def __hash__(self):
            return id(self)

    class AsyncCloseObj:
        async def aclose(self):
            markers["aclose"] += 1

    async def async_close():
        markers["async_close"] += 1

    async def async_shutdown():
        markers["async_shutdown"] += 1

    class SyncClose:
        def close(self):
            markers["sync_close"] += 1

    class SyncShutdown:
        def shutdown(self):
            markers["sync_shutdown"] += 1

    class ErrorCloser:
        def close(self):
            raise RuntimeError("boom")

    reg.track_closer(AsyncCloseObj())
    reg.track_closer(HashableNamespace(close=async_close))
    reg.track_closer(HashableNamespace(shutdown=async_shutdown))
    reg.track_closer(SyncClose())
    reg.track_closer(SyncShutdown())
    reg.track_closer(ErrorCloser())

    await reg.shutdown()

    assert task.cancelled()
    assert markers == {
        "aclose": 1,
        "async_close": 1,
        "async_shutdown": 1,
        "sync_close": 1,
        "sync_shutdown": 1,
    }
    assert reg._tasks == set()
    assert reg._closers == set()


@pytest.mark.asyncio
async def test_periodic_task_records_failures():
    reg = AsyncResourceRegistry()
    seen = {"failures": 0}

    async def boom():
        seen["failures"] += 1
        raise RuntimeError("boom")

    task = PeriodicTask(boom, 0.01, reg, name="boom")
    task.start()

    await asyncio.sleep(0.05)
    await task.stop()
    await reg.shutdown()

    assert task.failure_count >= 1
    assert seen["failures"] >= 1
