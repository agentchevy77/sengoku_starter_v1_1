import asyncio

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
