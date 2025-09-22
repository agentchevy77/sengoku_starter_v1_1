from __future__ import annotations

import heapq
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    __slots__ = (
        "_store",
        "_ttl",
        "_max",
        "_now",
        "_heap",
        "_stats",
        "_entry_finder",
        "_seq",
        "_removed_marker",
        "_heap_compaction_factor",
        "_heap_compaction_slack",
    )

    def __init__(
        self,
        max_items: int = 512,
        default_ttl_sec: int = 180,
        heap_compaction_factor: float = 3.0,
        heap_compaction_slack: int = 16,
    ) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = default_ttl_sec
        self._max = max(0, int(max_items))
        self._now = time.monotonic
        self._heap: list[list[Any]] = []
        self._stats: dict[str, float | int] = {
            "expired": 0,
            "capacity": 0,
            "hits": 0,
            "misses": 0,
            "heap_compactions": 0,
            "tombstone_ratio": 0.0,
        }
        self._entry_finder: dict[str, list[Any]] = {}
        self._seq = 0
        self._removed_marker: object = object()
        self._heap_compaction_factor = max(0.0, float(heap_compaction_factor))
        self._heap_compaction_slack = max(0, int(heap_compaction_slack))

    # ---- internal helpers ----
    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _push_entry(self, key: str, exp: float) -> None:
        entry = [exp, self._next_seq(), key]
        self._entry_finder[key] = entry
        heapq.heappush(self._heap, entry)

    def _invalidate_entry(self, key: str) -> None:
        entry = self._entry_finder.pop(key, None)
        if entry is not None:
            entry[2] = self._removed_marker

    def _prune_heap(self) -> None:
        while self._heap:
            _exp, _seq, key = self._heap[0]
            if key is self._removed_marker:
                heapq.heappop(self._heap)
                continue
            active = self._entry_finder.get(key)
            if active is not self._heap[0]:
                heapq.heappop(self._heap)
                continue
            break

    def _maybe_compact_heap(self) -> None:
        heap_size = len(self._heap)
        if not heap_size:
            self._stats["tombstone_ratio"] = 0.0
            return

        active = len(self._entry_finder)
        threshold = int(active * self._heap_compaction_factor + self._heap_compaction_slack)
        if heap_size > threshold:
            before = heap_size
            self._heap = [
                entry for entry in self._heap if entry[2] is not self._removed_marker and entry[2] in self._entry_finder
            ]
            removed = before - len(self._heap)
            if removed > 0:
                self._stats["heap_compactions"] += 1
            if self._heap:
                heapq.heapify(self._heap)
            heap_size = len(self._heap)

        tombstones = max(0, heap_size - active)
        self._stats["tombstone_ratio"] = (tombstones / heap_size) if heap_size else 0.0

    def _evict_expired(self, now: float) -> int:
        removed = 0
        while self._heap:
            self._prune_heap()
            if not self._heap:
                break
            exp, _seq, key = self._heap[0]
            if exp > now:
                break
            heapq.heappop(self._heap)
            data = self._store.get(key)
            if data is None:
                self._entry_finder.pop(key, None)
                continue
            if data[0] <= now:
                self._store.pop(key, None)
                self._entry_finder.pop(key, None)
                removed += 1
        if removed:
            self._stats["expired"] += removed
            logger.debug("TTLCache expired %d entries", removed)
        self._maybe_compact_heap()
        return removed

    def _ensure_capacity(self, now: float) -> None:
        self._evict_expired(now)
        while len(self._store) >= self._max and self._heap:
            self._prune_heap()
            if not self._heap:
                break
            exp, _seq, key = heapq.heappop(self._heap)
            data = self._store.get(key)
            if data is None:
                self._entry_finder.pop(key, None)
                continue
            if data[0] != exp:
                continue
            self._store.pop(key, None)
            self._entry_finder.pop(key, None)
            self._stats["capacity"] += 1
            logger.debug("TTLCache evicted '%s' due to capacity", key)
        self._maybe_compact_heap()

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            self._stats["misses"] += 1
            return None

        exp, val = item
        now = self._now()
        if now > exp:
            self._stats["misses"] += 1
            self._stats["expired"] += 1
            self._store.pop(key, None)
            self._invalidate_entry(key)
            self._maybe_compact_heap()
            return None

        self._stats["hits"] += 1
        return val

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = self._ttl if ttl is None else ttl
        now = self._now()
        exp = now + ttl
        if key in self._store:
            self._store[key] = (exp, value)
            self._invalidate_entry(key)
            self._push_entry(key, exp)
            self._prune_heap()
            self._maybe_compact_heap()
            return
        if self._max > 0 and len(self._store) >= self._max:
            self._ensure_capacity(now)
        if self._max == 0:
            return
        self._store[key] = (exp, value)
        self._push_entry(key, exp)
        self._prune_heap()
        self._maybe_compact_heap()

    def purge_expired(self) -> int:
        now = self._now()
        return self._evict_expired(now)

    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, float | int]:
        heap_size = len(self._heap)
        active = len(self._entry_finder)
        tombstones = max(0, heap_size - active)
        self._stats["tombstone_ratio"] = (tombstones / heap_size) if heap_size else 0.0
        out = dict(self._stats)
        out["heap_entries"] = heap_size
        out["active_entries"] = active
        out["size"] = len(self._store)
        return out
