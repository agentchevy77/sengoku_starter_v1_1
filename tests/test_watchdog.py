from __future__ import annotations

import time

from optipanel.runtime.watchdog import TwsWatchdog


def _wait_for(condition, *, timeout: float = 0.75, interval: float = 0.01) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("condition not met within timeout")


class FlipFetcher:
    def __init__(self, *, initial_up: bool = True) -> None:
        self.up = initial_up

    def handshake_test(self) -> dict[str, str]:
        return {"handshake": "ok"} if self.up else {}


def test_watchdog_emits_transitions():
    fetcher = FlipFetcher()
    events: list[tuple[str, str]] = []

    watchdog = TwsWatchdog(
        fetcher,
        interval_sec=0.05,
        on_up=lambda info: events.append(("up", info.get("handshake", ""))),
        on_down=lambda err: events.append(("down", err)),
    )

    watchdog.start()
    _wait_for(lambda: any(e[0] == "up" for e in events))

    fetcher.up = False
    _wait_for(lambda: any(e[0] == "down" for e in events))

    fetcher.up = True
    _wait_for(lambda: len([e for e in events if e[0] == "up"]) >= 2)

    watchdog.stop()

    ups = [e for e in events if e[0] == "up"]
    downs = [e for e in events if e[0] == "down"]

    assert len(ups) >= 2  # initial up + recovery
    assert len(downs) >= 1

    snap = watchdog.snapshot()
    assert snap.state in {"up", "down"}
    assert isinstance(snap.interval_sec, float)


def test_watchdog_records_errors_only_once():
    fetcher = FlipFetcher(initial_up=False)
    down_events: list[str] = []

    watchdog = TwsWatchdog(
        fetcher,
        interval_sec=0.05,
        on_down=lambda err: down_events.append(err),
    )

    watchdog.start()
    _wait_for(lambda: len(down_events) == 1)

    # keep failing - should not emit additional events until recovery
    time.sleep(0.15)
    assert len(down_events) == 1

    fetcher.up = True
    time.sleep(0.2)
    fetcher.up = False
    _wait_for(lambda: len(down_events) >= 2)

    watchdog.stop()
    assert len(down_events) >= 2  # down event after recovery and failure
