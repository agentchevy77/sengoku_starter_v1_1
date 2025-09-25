from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from optipanel.services.cache import TTLCache
from optipanel.services.leakguard import AsyncResourceRegistry, PeriodicTask

logger = logging.getLogger(__name__)


@dataclass
class Scheduler:
    registry: AsyncResourceRegistry
    cache: TTLCache
    tasks: dict[str, PeriodicTask] = field(default_factory=dict)

    def add_job(self, name: str, interval_sec: float, coro_func: Callable[[], Awaitable[None]]) -> None:
        task = PeriodicTask(coro_func, interval_sec, self.registry, name=name)
        if name in self.tasks:
            logger.info("Scheduler replacing task '%s'", name)
            old_task = self.tasks.pop(name)

            async def _stop_and_log(pt: PeriodicTask) -> None:
                try:
                    await pt.stop()
                finally:
                    logger.info("Scheduler stopped task '%s'", pt.name)

            asyncio.create_task(_stop_and_log(old_task))
        self.tasks[name] = task
        logger.info("Scheduler starting task '%s' interval=%.3fs", name, interval_sec)
        task.start()

    async def stop(self):
        logger.info("Scheduler stopping %d tasks", len(self.tasks))
        for t in list(self.tasks.values()):
            await t.stop()
        self.tasks.clear()
        await self.registry.shutdown()
