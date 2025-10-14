# Technical Report: From Bug Fixes to a Resilient Foundation

## 1. Executive Summary

This report details a two-phase campaign to improve the stability and architecture of the `optipanel` codebase. Phase 1 focused on the remediation of critical bugs identified in the initial analysis. Phase 2 marks a strategic shift from simple bug fixing to a more robust architectural reconstruction, with the first target being the TWS data fetcher.

This document outlines the key fixes implemented, the design of the new asynchronous `AsyncTwsFetcher`, and the verification strategy employed to ensure its resilience. The goal is to use the lessons from the initial failures to build a more stable and maintainable foundation for future development.

## 2. Phase 1: Critical Bug Remediation

The initial phase was a targeted effort to address a series of critical vulnerabilities that threatened the stability of the application. The following sections detail the most significant fixes.

### 2.1. Cache Race Condition and Thread Safety

-   **Problem:** The `_TickCache._prune_expired` method in `optipanel/api/app.py` was not thread-safe, creating a risk of race conditions during cache pruning.
-   **Solution:** The method was refactored to iterate over a copy of the cache items, ensuring that the collection is not modified during iteration. This was done while preserving the LRU logic.

```python
# In optipanel/api/app.py

def _prune_expired(self, now: float) -> None:
    """Prune expired entries efficiently."""
    with self._lock:
        # Iterate over a copy of items to prevent race conditions
        for k, v in list(self._data.items()):
            if v.expires_at <= now:
                self._data.pop(k, None)
                try:
                    self._keys.remove(k)
                except ValueError:
                    pass
```

### 2.2. TWS Fetcher Thread Leak

-   **Problem:** The `RealTwsFetcher._connect` method in `optipanel/adapters/ibkr/tws_fetcher.py` created a daemon thread that was not properly terminated on connection timeout, leading to a critical thread leak.
-   **Solution:** The thread was changed to a non-daemon thread, and `thread.join()` is now called in all failure paths to ensure the thread is cleaned up before proceeding.

```python
# In optipanel/adapters/ibkr/tws_fetcher.py

def _connect(self) -> _HistApp:
    # ...
    thread = threading.Thread(target=app.run, name="tws-run", daemon=False)
    thread.start()
    if not app.ready.wait(self.cfg.handshake_timeout):
        app.disconnect()
        if thread:
            thread.join(timeout=1.0)
        # ...
```

### 2.3. Unsafe Type Conversions in CLI

-   **Problem:** The `optipanel/cli/main.py` module used direct `int()` conversions for environment variables, creating a crash risk if the variables were not set or contained non-numeric values.
-   **Solution:** The unsafe conversions were replaced with the existing `safe_int()` utility, which provides a default fallback and prevents crashes.

```python
# In optipanel/cli/main.py

# In notify_main:
ready_min = args.ready_min if args.ready_min is not None else safe_int(env_ready, 65)

# In profiles_live_cmd:
port = safe_int(port_env, 7496)
client_id = safe_int(client_env, 107)
```

### 2.4. Hardcoded Thresholds in Setups Engine

-   **Problem:** The `compute_setups` function in `optipanel/setups/engine.py` contained numerous hardcoded "magic numbers," making the logic difficult to understand and tune.
-   **Solution:** A `SetupConfig` dataclass was introduced to encapsulate all thresholds. The `compute_setups` function was refactored to accept this config object, making the engine configurable and its logic transparent.

```python
# In optipanel/setups/engine.py

@dataclass
class SetupConfig:
    breakout_gap_threshold: float = 0.01
    breakout_base_near: float = 60.0
    # ... all other thresholds ...

def compute_setups(features: dict[str, Any], config: SetupConfig | None = None) -> dict[str, int]:
    if config is None:
        config = SetupConfig()
    # ... logic now uses config.breakout_gap_threshold, etc. ...
```

## 3. Phase 2: Architectural Reconstruction

With the critical bugs addressed, the project has moved to a reconstruction phase. The first target is the `TwsFetcher`, which is being rebuilt from the ground up with a focus on resilience, asynchronicity, and observability.

### 3.1. The `AsyncTwsFetcher` Blueprint

A new file, `optipanel/adapters/ibkr/tws_fetcher_v2.py`, has been created to house the new implementation. The design is centered around the `TwsFetcherInterface` abstract base class and the `AsyncTwsFetcher` concrete implementation.

**Core Design Principles:**

-   **Asynchronous:** The entire fetcher is built on `asyncio` to ensure non-blocking I/O and high performance.
-   **Self-Healing:** A persistent background task manages the connection, automatically reconnecting on failure.
-   **Resilience:** Partial failures in batch requests are handled gracefully using a generic `Result` object.
-   **Observability:** A `TwsFetcherStatus` dataclass provides real-time insight into the fetcher's health.

### 3.2. Key Implementation Details

-   **Connection Management:** The `start()` method launches a background `_heartbeat` task that manages the connection lifecycle, including a retry mechanism with exponential backoff.

-   **Concurrent & Resilient Fetching:** The `fetch_features` method uses `asyncio.gather` to execute requests concurrently. Each request is wrapped in a `Result` object to isolate failures.

-   **Caching:** The implementation uses `async_lru` to cache both feature data and contract qualifications, preventing the "Thundering Herd" problem and improving efficiency.

-   **Rate Limiting:** An `aiolimiter.AsyncLimiter` is used to ensure that the rate of requests to the TWS API does not exceed the configured limit.

### 3.3. Verification Strategy

A new test suite, `tests/test_tws_fetcher_v2.py`, has been created to verify the new implementation. The tests are designed to validate:

-   Correct lifecycle management (`start`/`stop` and self-healing reconnection).
-   The caching layer's defense against the "Thundering Herd".
-   Graceful handling of partial failures.
-   The precision of the asynchronous rate limiter.

## 4. Current Status and Next Steps

The implementation of the `AsyncTwsFetcher` is complete. We are currently in the process of verifying its correctness and resilience through the new test suite. The initial test runs have been hampered by external factors, but the path forward is to complete this verification. Once the `AsyncTwsFetcher` is fully verified, the next step will be to integrate it into the application, replacing the old `RealTwsFetcher`.