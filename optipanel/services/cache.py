from __future__ import annotations

import heapq
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    __slots__ = ("_store", "_ttl", "_max", "_now", "_heap", "_stats")

    def __init__(self, max_items: int = 512, default_ttl_sec: int = 180) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = default_ttl_sec
        self._max = max(0, int(max_items))
        self._now = time.monotonic
        self._heap: list[tuple[float, str]] = []
        self._stats: dict[str, int] = {"expired": 0, "capacity": 0}

    def _evict_expired(self, now: float) -> int:
        removed = 0
        while self._heap:
            exp, key = self._heap[0]
            if exp > now:
                break
            heapq.heappop(self._heap)
            data = self._store.get(key)
            if data is None:
                continue
            if data[0] <= now:
                self._store.pop(key, None)
                removed += 1
        if removed:
            self._stats["expired"] += removed
            logger.debug("TTLCache expired %d entries", removed)
        return removed

    def _ensure_capacity(self, now: float) -> None:
        self._evict_expired(now)
        while len(self._store) >= self._max and self._heap:
            exp, key = heapq.heappop(self._heap)
            data = self._store.get(key)
            if data is None:
                continue
            if data[0] != exp:
                heapq.heappush(self._heap, (data[0], key))
                continue
            self._store.pop(key, None)
            self._stats["capacity"] += 1
            logger.debug("TTLCache evicted '%s' due to capacity", key)

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        exp, val = item
        now = self._now()
        if now > exp:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = self._ttl if ttl is None else ttl
        now = self._now()
        exp = now + ttl
        if key in self._store:
            self._store[key] = (exp, value)
            heapq.heappush(self._heap, (exp, key))
            return
        if self._max > 0 and len(self._store) >= self._max:
            self._ensure_capacity(now)
        if self._max == 0:
            return
        self._store[key] = (exp, value)
        heapq.heappush(self._heap, (exp, key))

    def purge_expired(self) -> int:
        now = self._now()
        return self._evict_expired(now)

    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, int]:
        return dict(self._stats)
