from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Dict
from optipanel.services.leakguard import AsyncResourceRegistry, PeriodicTask
from optipanel.services.cache import TTLCache

@dataclass
class Scheduler:
    registry: AsyncResourceRegistry
    cache: TTLCache
    tasks: Dict[str, PeriodicTask] = field(default_factory=dict)

    def add_job(self, name: str, interval_sec: float, coro_func: Callable[[], Awaitable[None]]) -> None:
        task = PeriodicTask(coro_func, interval_sec, self.registry, name=name)
        if name in self.tasks:
            asyncio.create_task(self.tasks[name].stop())
        self.tasks[name] = task
        task.start()

    async def stop(self):
        for t in list(self.tasks.values()): await t.stop()
        self.tasks.clear()
        await self.registry.shutdown()
