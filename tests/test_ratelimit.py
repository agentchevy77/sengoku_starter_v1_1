import pytest

from optipanel.services.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_rate_limiter_throttles_requests():
    clock = FakeClock()
    sleeps: list[float] = []

    def sleeper(duration: float) -> None:
        sleeps.append(duration)
        clock.advance(duration)

    limiter = RateLimiter(max_calls=2, interval_sec=4.0, clock=clock.time, sleeper=sleeper, name="test")

    assert limiter.acquire() == pytest.approx(0.0)
    assert limiter.acquire() == pytest.approx(0.0)

    waited = limiter.acquire()
    assert waited == pytest.approx(2.0)
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(2.0)
    assert limiter.available() == pytest.approx(0.0)

    clock.advance(4.0)
    assert limiter.available() == pytest.approx(2.0)


def test_rate_limiter_disabled_allows_unlimited():
    limiter = RateLimiter(max_calls=0, interval_sec=10.0)
    assert limiter.acquire() == 0.0
    assert limiter.acquire() == 0.0
    assert limiter.available() == float("inf")
