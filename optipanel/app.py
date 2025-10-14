from __future__ import annotations

import asyncio

try:  # pragma: no cover - exercised only when uvloop is installed
    import uvloop
except Exception:  # pragma: no cover - fallback to default loop
    pass
else:  # pragma: no cover - trivial branch once imported
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import signal

from optipanel.adapters.ibkr.sandbox import SandboxAdapter
from optipanel.services.cache import TTLCache
from optipanel.services.leakguard import AsyncResourceRegistry
from optipanel.services.scheduler import Scheduler
from optipanel.settings import load_settings


async def main():
    settings = load_settings()
    cache = TTLCache(max_items=settings.cache_max_items, default_ttl_sec=settings.cache_default_ttl_sec)
    registry = AsyncResourceRegistry()
    sched = Scheduler(registry=registry, cache=cache)
    adapter = SandboxAdapter()

    symbols_prime = ["AAPL", "NVDA", "MSFT"]
    symbols_secondary = ["AMD", "META", "TSLA", "GOOGL"]

    async def prime_tick():
        for sym in symbols_prime:
            snap = await adapter.get_underlying_snapshot(sym)
            cache.set(f"snap:{sym}", snap, ttl=60)

    async def secondary_thin_tick():
        sym = symbols_secondary.pop(0)
        symbols_secondary.append(sym)
        snap = await adapter.get_underlying_snapshot(sym)
        cache.set(f"thin:{sym}", snap, ttl=120)

    sched.add_job("prime", settings.prime_interval_sec, prime_tick)
    sched.add_job("secondary-thin", settings.secondary_thin_interval_sec, secondary_thin_tick)

    print("Sengoku starter running (v1.1). Press Ctrl+C to stop.")
    stop_event = asyncio.Event()

    def _sig(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig)
    await stop_event.wait()
    await sched.stop()


if __name__ == "__main__":
    asyncio.run(main())
