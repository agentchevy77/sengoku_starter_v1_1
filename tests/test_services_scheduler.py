import asyncio

import pytest

from optipanel.services.cache import TTLCache
from optipanel.services.leakguard import AsyncResourceRegistry
from optipanel.services.scheduler import Scheduler


@pytest.mark.asyncio
async def test_scheduler_add_job_runs_and_stop_cleans_up():
    reg = AsyncResourceRegistry()
    cache = TTLCache(max_items=8, default_ttl_sec=30)
    scheduler = Scheduler(registry=reg, cache=cache)

    ran = []
    ready = asyncio.Event()

    async def job():
        ran.append(asyncio.get_running_loop().time())
        ready.set()

    scheduler.add_job("prime", 0.01, job)

    await asyncio.wait_for(ready.wait(), timeout=0.2)

    assert "prime" in scheduler.tasks
    assert scheduler.tasks["prime"].failure_count == 0
    assert ran

    await scheduler.stop()

    assert scheduler.tasks == {}
    assert reg._tasks == set()
    assert reg._closers == set()


@pytest.mark.asyncio
async def test_scheduler_job_failure_logged_and_recovers(caplog):
    reg = AsyncResourceRegistry()
    cache = TTLCache(max_items=4, default_ttl_sec=10)
    scheduler = Scheduler(registry=reg, cache=cache)

    runs = {"count": 0}
    healthy = asyncio.Event()

    async def flaky_job():
        runs["count"] += 1
        if runs["count"] == 1:
            raise RuntimeError("boom")
        healthy.set()

    with caplog.at_level("ERROR"):
        scheduler.add_job("noisy", 0.01, flaky_job)
        await asyncio.wait_for(healthy.wait(), timeout=0.5)

    task = scheduler.tasks["noisy"]
    assert task.failure_count >= 1
    assert any("PeriodicTask noisy failure" in rec.message for rec in caplog.records)

    await scheduler.stop()


class RecordingRegistry(AsyncResourceRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.tracked: list[asyncio.Task] = []

    def track_task(self, task: asyncio.Task) -> None:  # pragma: no cover - exercised in tests
        self.tracked.append(task)
        super().track_task(task)


@pytest.mark.asyncio
async def test_scheduler_replacement_tracks_cleanup_tasks():
    reg = RecordingRegistry()
    cache = TTLCache(max_items=4, default_ttl_sec=10)
    scheduler = Scheduler(registry=reg, cache=cache)

    async def job():
        await asyncio.sleep(0)

    scheduler.add_job("prime", 0.01, job)
    await asyncio.sleep(0.05)

    scheduler.add_job("prime", 0.01, job)

    assert reg.tracked, "replacement should track cleanup tasks"

    await scheduler.stop()
