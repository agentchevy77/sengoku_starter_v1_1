from __future__ import annotations
import asyncio, tracemalloc, contextlib
from dataclasses import dataclass
from typing import Any, Set

@dataclass
class LeakSentinel:
    label: str = "leak-check"
    budget_bytes: int = 1_000_000
    def __enter__(self):
        tracemalloc.start(); self._snap_a = tracemalloc.take_snapshot(); return self
    def __exit__(self, exc_type, exc, tb):
        snap_b = tracemalloc.take_snapshot()
        total = sum(s.size_diff for s in snap_b.compare_to(self._snap_a, "lineno"))
        tracemalloc.stop()
        if total > self.budget_bytes:
            raise AssertionError(f"Memory grew by {total} bytes (> {self.budget_bytes}) in {self.label}")

class AsyncResourceRegistry:
    def __init__(self):
        self._tasks: Set[asyncio.Task] = set()
        self._closers: Set[Any] = set()

    def track_task(self, task: asyncio.Task) -> None: self._tasks.add(task)
    def track_closer(self, obj: Any) -> None: self._closers.add(obj)

    async def shutdown(self, *, timeout: float = 5.0) -> None:
        for t in list(self._tasks):
            if not t.done(): t.cancel()
        if self._tasks: await asyncio.gather(*self._tasks, return_exceptions=True)
        for c in list(self._closers):
            try:
                meth = None
                if hasattr(c,"aclose"): meth = c.aclose
                elif hasattr(c,"close") and asyncio.iscoroutinefunction(c.close): meth = c.close
                elif hasattr(c,"shutdown") and asyncio.iscoroutinefunction(c.shutdown): meth = c.shutdown
                if meth: await meth()
            except Exception: pass
        self._tasks.clear(); self._closers.clear()

class PeriodicTask:
    def __init__(self, coro_func, interval_sec: float, registry: AsyncResourceRegistry, name: str):
        self.coro_func=coro_func; self.interval=interval_sec; self.registry=registry; self.name=name
        self._stop=asyncio.Event(); self._task: asyncio.Task|None=None
    def start(self):
        if self._task and not self._task.done(): return
        self._task=asyncio.create_task(self._run(), name=self.name); self.registry.track_task(self._task)
    async def _run(self):
        try:
            while not self._stop.is_set():
                await self.coro_func()
                try: await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
                except asyncio.TimeoutError: pass
        except asyncio.CancelledError: pass
    async def stop(self):
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(Exception): await self._task
        self._task=None
