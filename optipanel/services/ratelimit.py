from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass
class RateLimiter:
    """Token-bucket rate limiter suitable for IO pacing."""

    max_calls: int
    interval_sec: float
    clock: Clock = time.monotonic
    sleeper: Sleeper = time.sleep
    name: str | None = None

    def __post_init__(self) -> None:
        self._enabled = self.max_calls > 0 and self.interval_sec > 0
        if not self._enabled:
            self._capacity = 0.0
            self._refill_per_sec = 0.0
            self._tokens = float("inf")
            self._last_refill = self.clock()
            return
        self._capacity = float(self.max_calls)
        self._refill_per_sec = self._capacity / float(self.interval_sec)
        self._tokens = self._capacity
        self._last_refill = self.clock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def acquire(self, tokens: float = 1.0) -> float:
        if tokens <= 0:
            return 0.0
        if not self._enabled:
            return 0.0
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return 0.0
        deficit = tokens - self._tokens
        wait_for = deficit / self._refill_per_sec
        if wait_for > 0:
            self.sleeper(wait_for)
        self._refill()
        self._tokens = max(0.0, self._tokens - tokens)
        logger.debug(
            "RateLimiter %s throttled for %.3fs (tokens=%.2f capacity=%.2f)",
            self.name or "",
            max(wait_for, 0.0),
            tokens,
            self._capacity,
        )
        return max(wait_for, 0.0)

    def available(self) -> float:
        if not self._enabled:
            return float("inf")
        self._refill()
        return self._tokens

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self._last_refill)
        if not elapsed:
            return
        if self._enabled:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_sec)
        self._last_refill = now
