from optipanel.services.cache import TTLCache
import time
def test_ttlcache_expiry_and_evict():
    c = TTLCache(max_items=3, default_ttl_sec=1)
    c.set("a",1); c.set("b",2); c.set("c",3)
    assert c.size() == 3
    time.sleep(1.2)
    assert c.get("a") is None
    c.set("d",4)
    assert c.size() <= 3
