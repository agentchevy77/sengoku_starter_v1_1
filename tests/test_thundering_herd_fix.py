"""
Test suite validating Bug #7 fix: Thundering Herd Prevention in _TickCache

This module contains tests that specifically validate that the _TickCache
properly prevents thundering herd scenarios when the loader fails.

HISTORICAL CONTEXT (Bug #7):
===============================
The original implementation allowed multiple threads to simultaneously retry
a failed loader, defeating the cache's concurrency control purpose:

    except Exception:
        with self._lock:
            event = self._inflight.pop(key, None)
            if event is not None:
                event.set()  # All waiters wake up
        raise

    # All waiters loop back, find waiter is None, ALL become loaders!

This created a stampede on the failing backend, multiplying load by N threads.

THE FIX:
========
Introduced failure cooldown tracking:
1. When loader fails, set _failure_cooldowns[key] = now + 5.0 seconds
2. When thread tries to become loader, check cooldown first
3. If in cooldown, raise RuntimeError with "retry in X seconds"
4. Only first thread after cooldown can retry

This prevents thundering herd while maintaining simple, zero-config semantics.
"""

import threading
import time
from typing import Any

import pytest

from optipanel.api.app import _TickCache


def test_thundering_herd_prevented_on_loader_failure():
    """
    Prove that when loader fails, waiting threads don't stampede to retry.

    This is the core bug fix validation: multiple threads waiting for the same
    key should NOT all retry when the loader fails.
    """
    cache = _TickCache()
    cache.clear()

    call_count = {"count": 0}
    call_lock = threading.Lock()
    failure_count = 5  # Fail first 5 attempts

    def failing_loader() -> dict[str, Any]:
        nonlocal call_count
        with call_lock:
            call_count["count"] += 1
            if call_count["count"] <= failure_count:
                raise RuntimeError(f"Simulated backend failure #{call_count['count']}")
        # Success after failure_count attempts
        return {"value": "success"}

    results: list[tuple[str, Any]] = []  # (status, value_or_error)

    def worker(worker_id: int) -> None:
        try:
            result = cache.get_or_create(("test_key",), ttl=60.0, loader=failing_loader)
            results.append(("success", result))
        except Exception as e:
            results.append(("error", str(e)))

    # Launch 10 threads simultaneously
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    # CRITICAL ASSERTION: Without fix, all 10 threads would call loader
    # With fix, only the first thread calls loader, others get cooldown error
    assert call_count["count"] == 1, (
        f"Expected exactly 1 loader call (first thread), got {call_count['count']}. "
        "This indicates thundering herd is NOT prevented!"
    )

    # Verify exactly 1 thread got the loader failure
    loader_failures = [r for r in results if r[0] == "error" and "Simulated backend failure" in r[1]]
    assert len(loader_failures) == 1, f"Expected 1 loader failure, got {len(loader_failures)}"

    # Verify remaining 9 threads got cooldown errors
    cooldown_errors = [r for r in results if r[0] == "error" and "retry in" in r[1]]
    assert len(cooldown_errors) == 9, f"Expected 9 cooldown errors (waiting threads), got {len(cooldown_errors)}"


def test_cooldown_clears_after_timeout():
    """
    Verify that cooldown expires and allows retry after configured timeout.
    """
    cache = _TickCache()
    cache.clear()
    cache._failure_cooldown_sec = 0.1  # Short cooldown for test speed

    call_count = {"count": 0}

    def failing_once_loader() -> dict[str, Any]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("First call fails")
        return {"value": call_count["count"]}

    # First call fails
    with pytest.raises(RuntimeError, match="First call fails"):
        cache.get_or_create(("key",), ttl=10.0, loader=failing_once_loader)

    assert call_count["count"] == 1

    # Immediate retry should hit cooldown
    with pytest.raises(RuntimeError, match="retry in"):
        cache.get_or_create(("key",), ttl=10.0, loader=failing_once_loader)

    # Still only 1 call (second call blocked by cooldown)
    assert call_count["count"] == 1

    # Wait for cooldown to expire
    time.sleep(0.15)

    # Now retry should succeed
    result = cache.get_or_create(("key",), ttl=10.0, loader=failing_once_loader)
    assert result == {"value": 2}
    assert call_count["count"] == 2


def test_cooldown_is_per_key():
    """
    Verify that cooldown is tracked per key, not globally.
    """
    cache = _TickCache()
    cache.clear()

    def failing_loader() -> dict[str, Any]:
        raise RuntimeError("Always fails")

    def success_loader() -> dict[str, Any]:
        return {"value": "ok"}

    # Fail key1
    with pytest.raises(RuntimeError, match="Always fails"):
        cache.get_or_create(("key1",), ttl=10.0, loader=failing_loader)

    # key1 should be in cooldown
    with pytest.raises(RuntimeError, match="retry in"):
        cache.get_or_create(("key1",), ttl=10.0, loader=failing_loader)

    # key2 should NOT be affected (different key)
    result = cache.get_or_create(("key2",), ttl=10.0, loader=success_loader)
    assert result == {"value": "ok"}


def test_successful_load_clears_cooldown():
    """
    Verify that successful load after cooldown clears the cooldown state.
    """
    cache = _TickCache()
    cache.clear()
    cache._failure_cooldown_sec = 0.05

    call_count = {"count": 0}

    def flaky_loader() -> dict[str, Any]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("First fails")
        return {"value": "success"}

    # First call fails, sets cooldown
    with pytest.raises(RuntimeError, match="First fails"):
        cache.get_or_create(("key",), ttl=10.0, loader=flaky_loader)

    # Verify cooldown exists
    assert ("key",) in cache._failure_cooldowns

    # Wait for cooldown
    time.sleep(0.1)

    # Successful load
    result = cache.get_or_create(("key",), ttl=10.0, loader=flaky_loader)
    assert result == {"value": "success"}

    # Cooldown should be cleared (removed from dict, not just expired)
    assert ("key",) not in cache._failure_cooldowns


def test_cooldown_pruning():
    """
    Verify that expired cooldowns are pruned during periodic maintenance.
    """
    cache = _TickCache()
    cache.clear()
    cache._failure_cooldown_sec = 0.01  # Very short cooldown
    cache._prune_interval = 0.0  # Force pruning on every operation

    def failing_loader() -> dict[str, Any]:
        raise RuntimeError("Fail")

    # Create failure cooldown for key1
    with pytest.raises(RuntimeError, match="Fail"):
        cache.get_or_create(("key1",), ttl=1.0, loader=failing_loader)

    assert ("key1",) in cache._failure_cooldowns

    # Wait for cooldown to expire
    time.sleep(0.02)

    # Trigger prune by accessing cache (prune happens on get_or_create)
    # Use different key to avoid triggering the cooldown check path
    def success_loader() -> dict[str, Any]:
        return {"ok": True}

    cache.get_or_create(("key2",), ttl=1.0, loader=success_loader)

    # Expired cooldown should be pruned
    assert ("key1",) not in cache._failure_cooldowns


def test_cache_clear_removes_cooldowns():
    """
    Verify that cache.clear() also clears failure cooldowns.
    """
    cache = _TickCache()
    cache.clear()

    def failing_loader() -> dict[str, Any]:
        raise RuntimeError("Fail")

    # Create failure cooldown
    with pytest.raises(RuntimeError, match="Fail"):
        cache.get_or_create(("key1",), ttl=10.0, loader=failing_loader)

    assert len(cache._failure_cooldowns) > 0

    # Clear cache
    cache.clear()

    # Cooldowns should be cleared
    assert len(cache._failure_cooldowns) == 0


def test_concurrent_retries_after_cooldown():
    """
    Verify that after cooldown expires, only ONE thread retries (not all).

    This is subtle: when cooldown expires, multiple threads might race to become
    the loader. We need to ensure only one wins, others wait.
    """
    cache = _TickCache()
    cache.clear()
    cache._failure_cooldown_sec = 0.05

    call_count = {"count": 0}
    call_lock = threading.Lock()

    def flaky_loader() -> dict[str, Any]:
        with call_lock:
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise RuntimeError("First fails")
        # Add small delay to ensure multiple threads reach this point
        time.sleep(0.01)
        return {"value": call_count["count"]}

    # First thread fails, sets cooldown
    with pytest.raises(RuntimeError, match="First fails"):
        cache.get_or_create(("key",), ttl=10.0, loader=flaky_loader)

    assert call_count["count"] == 1

    # Wait for cooldown to expire
    time.sleep(0.1)

    # Now launch 5 threads simultaneously
    results: list[dict[str, Any]] = []

    def worker() -> None:
        result = cache.get_or_create(("key",), ttl=10.0, loader=flaky_loader)
        results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1.0)

    # CRITICAL: Only 1 additional loader call should happen (the retry)
    # The other 4 threads should wait for that loader to complete
    assert call_count["count"] == 2, f"Expected 2 total loader calls (1 failure + 1 retry), got {call_count['count']}"

    # All 5 threads should get the same successful result
    assert len(results) == 5
    assert all(r == {"value": 2} for r in results)


def test_cooldown_error_message_clarity():
    """
    Verify that cooldown error message is clear and actionable.
    """
    cache = _TickCache()
    cache.clear()

    def failing_loader() -> dict[str, Any]:
        raise RuntimeError("Backend error")

    # First call fails
    with pytest.raises(RuntimeError, match="Backend error"):
        cache.get_or_create(("mykey",), ttl=10.0, loader=failing_loader)

    # Second call should get clear cooldown message
    try:
        cache.get_or_create(("mykey",), ttl=10.0, loader=failing_loader)
        pytest.fail("Expected RuntimeError")
    except RuntimeError as e:
        error_msg = str(e)
        # Verify message contains key elements
        assert "retry in" in error_msg
        assert "thundering herd prevention" in error_msg
        # Should mention the key (truncated for privacy)
        assert "mykey" in error_msg or "('mykey',)" in error_msg


def test_backward_compatibility_success_path():
    """
    Verify that successful loader path is unchanged (no regression).
    """
    cache = _TickCache()
    cache.clear()

    call_count = {"count": 0}

    def success_loader() -> dict[str, Any]:
        call_count["count"] += 1
        time.sleep(0.01)
        return {"value": call_count["count"]}

    # Launch 10 concurrent threads
    results: list[dict[str, Any]] = []

    def worker() -> None:
        result = cache.get_or_create(("key",), ttl=60.0, loader=success_loader)
        results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1.0)

    # Original behavior: only 1 loader call, all threads get same result
    assert call_count["count"] == 1
    assert len(results) == 10
    assert all(r == {"value": 1} for r in results)


def test_documentation_of_bug_7():
    """
    Document what Bug #7 was and prove it's fixed with execution timeline.
    """
    # BUG #7 EXPLANATION
    # ===================
    # When loader() failed, the exception handler looked like:
    #
    #     except Exception:
    #         with self._lock:
    #             event = self._inflight.pop(key, None)
    #             if event is not None:
    #                 event.set()  # Wakes ALL waiting threads
    #         raise
    #
    # All waiting threads wake up, loop back to while True, find waiter is None,
    # and ALL become loaders simultaneously - thundering herd!
    #
    # THE FIX
    # =======
    # Added _failure_cooldowns dict to track recent failures:
    # 1. On failure: _failure_cooldowns[key] = now + 5.0
    # 2. Before becoming loader: check if now < _failure_cooldowns[key]
    # 3. If in cooldown: raise "retry in X seconds" error
    # 4. Waiting threads get immediate error, no stampede

    cache = _TickCache()
    cache.clear()

    execution_log: list[str] = []
    log_lock = threading.Lock()

    def log(msg: str) -> None:
        with log_lock:
            execution_log.append(msg)

    def failing_loader() -> dict[str, Any]:
        log("loader_called")
        raise RuntimeError("Simulated failure")

    def thread_a() -> None:
        log("thread_a_start")
        try:
            cache.get_or_create(("key",), ttl=10.0, loader=failing_loader)
        except RuntimeError as e:
            if "Simulated failure" in str(e):
                log("thread_a_loader_failed")
            else:
                log("thread_a_cooldown_error")

    def thread_b() -> None:
        # Start slightly after A to ensure A becomes loader
        time.sleep(0.01)
        log("thread_b_start")
        try:
            cache.get_or_create(("key",), ttl=10.0, loader=failing_loader)
        except RuntimeError as e:
            if "Simulated failure" in str(e):
                log("thread_b_loader_failed")
            else:
                log("thread_b_cooldown_error")

    ta = threading.Thread(target=thread_a)
    tb = threading.Thread(target=thread_b)

    ta.start()
    tb.start()
    ta.join(timeout=1.0)
    tb.join(timeout=1.0)

    # Verify execution order proves fix
    # Thread A should become loader and fail
    # Thread B should hit cooldown (NOT become loader)
    assert "thread_a_start" in execution_log
    assert "loader_called" in execution_log
    assert "thread_a_loader_failed" in execution_log
    assert "thread_b_start" in execution_log
    assert "thread_b_cooldown_error" in execution_log

    # Critical proof: loader called exactly once
    loader_calls = execution_log.count("loader_called")
    assert loader_calls == 1, f"Expected 1 loader call, got {loader_calls} - thundering herd NOT prevented!"
