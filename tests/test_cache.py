import time

from optipanel.services.cache import TTLCache


def test_ttlcache_expiry_and_evict():
    c = TTLCache(max_items=3, default_ttl_sec=1)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert c.size() == 3
    time.sleep(1.2)
    assert c.get("a") is None
    c.set("d", 4)
    assert c.size() <= 3


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def _patch_clock(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr("optipanel.services.cache.time.monotonic", clock)
    return clock


def test_set_refreshes_expiration_and_updates_value(monkeypatch):
    clock = _patch_clock(monkeypatch)
    cache = TTLCache(max_items=2, default_ttl_sec=10)

    cache.set("a", 1, ttl=5)
    clock.advance(4)
    assert cache.get("a") == 1

    cache.set("a", 2, ttl=5)
    clock.advance(4)
    assert cache.get("a") == 2  # refreshed expiry keeps entry alive

    clock.advance(6)
    assert cache.get("a") is None


def test_capacity_eviction_tracks_stats(monkeypatch):
    clock = _patch_clock(monkeypatch)
    cache = TTLCache(max_items=2, default_ttl_sec=30)

    cache.set("a", 1, ttl=30)
    clock.advance(1)
    cache.set("b", 2, ttl=30)
    clock.advance(1)
    cache.set("c", 3, ttl=30)

    assert cache.size() == 2
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.stats()["capacity"] == 1


def test_purge_expired_returns_removed_count(monkeypatch):
    clock = _patch_clock(monkeypatch)
    cache = TTLCache(max_items=3, default_ttl_sec=10)

    cache.set("a", 1, ttl=5)
    cache.set("b", 2, ttl=8)
    clock.advance(6)

    removed = cache.purge_expired()
    assert removed == 1
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.stats()["expired"] == 1


def test_zero_capacity_cache_ignores_writes(monkeypatch):
    _patch_clock(monkeypatch)
    cache = TTLCache(max_items=0, default_ttl_sec=10)

    cache.set("noop", "value")
    assert cache.size() == 0
    assert cache.get("noop") is None


def test_repeated_updates_do_not_bloat_heap(monkeypatch):
    _patch_clock(monkeypatch)
    cache = TTLCache(max_items=10, default_ttl_sec=120)

    for i in range(50):
        cache.set("symbol", i, ttl=60)

    assert cache.size() == 1
    assert cache.get("symbol") == 49
    assert len(cache._heap) <= 8  # internal structure stays compact


def test_hit_miss_metrics(monkeypatch):
    clock = _patch_clock(monkeypatch)
    cache = TTLCache(max_items=3, default_ttl_sec=10)

    cache.set("a", 1, ttl=5)
    assert cache.get("a") == 1

    clock.advance(6)
    assert cache.get("a") is None
    assert cache.get("missing") is None

    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2
    assert stats["expired"] == 1


def test_heap_compaction_metrics(monkeypatch):
    _patch_clock(monkeypatch)
    cache = TTLCache(
        max_items=6,
        default_ttl_sec=60,
        heap_compaction_factor=0.0,
        heap_compaction_slack=1,
    )

    cache.set("anchor_a", 1, ttl=40)
    cache.set("anchor_b", 2, ttl=40)

    for i in range(6):
        cache.set("key", i, ttl=40)

    stats = cache.stats()
    assert stats["heap_compactions"] >= 1
    assert stats["tombstone_ratio"] == 0.0
