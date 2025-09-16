from __future__ import annotations
import time
from typing import Any, Optional

class TTLCache:
    __slots__ = ("_store","_ttl","_max","_now")
    def __init__(self, max_items: int = 512, default_ttl_sec: int = 180) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = default_ttl_sec
        self._max = max_items
        self._now = time.monotonic

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item: return None
        exp, val = item
        if self._now() > exp:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if len(self._store) >= self._max:
            oldest = sorted(self._store.items(), key=lambda kv: kv[1][0])[: max(1, self._max // 10)]
            for k,_ in oldest: self._store.pop(k, None)
        ttl = self._ttl if ttl is None else ttl
        self._store[key] = (self._now() + ttl, value)

    def purge_expired(self) -> int:
        now = self._now()
        keys = [k for k,(exp,_) in self._store.items() if exp < now]
        for k in keys: self._store.pop(k, None)
        return len(keys)

    def size(self) -> int: return len(self._store)
