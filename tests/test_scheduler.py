import asyncio

from optipanel.services.cache import TTLCache
from optipanel.services.leakguard import AsyncResourceRegistry
from optipanel.services.scheduler import Scheduler


async def test_scheduler_start_stop():
    reg = AsyncResourceRegistry()
    cache = TTLCache()
    sched = Scheduler(registry=reg, cache=cache)

    calls = {"prime": 0, "sec": 0}

    async def prime():
        calls["prime"] += 1

    async def sec():
        calls["sec"] += 1

    sched.add_job("prime", 0.01, prime)
    sched.add_job("secondary", 0.02, sec)

    await asyncio.sleep(0.05)
    await sched.stop()
    assert calls["prime"] > 0 and calls["sec"] > 0
    assert reg._tasks == set()
