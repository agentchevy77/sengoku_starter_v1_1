"""Runtime watchdog utilities for monitoring IBKR/TWS connectivity.

Stage 3 focuses on hardening and observability.  The watchdog gives the
runtime a lightweight tool to poll ``fetcher.handshake_test`` on a cadence,
track transitions, and surface callbacks when connectivity changes state.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WatchdogSnapshot:
    """Immutable view of the last-known watchdog state."""

    up: bool
    state: str
    last_ok_at: float | None
    last_err_at: float | None
    last_error: str | None
    interval_sec: float

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - convenience helper
        return {
            "up": self.up,
            "state": self.state,
            "last_ok_at": self.last_ok_at,
            "last_err_at": self.last_err_at,
            "last_error": self.last_error,
            "interval_sec": self.interval_sec,
        }


class TwsWatchdog:
    """Poll ``fetcher.handshake_test`` on an interval and raise transition hooks.

    * ``fetcher.handshake_test`` must return a mapping that includes
      ``{"handshake": "ok"}`` when the session is healthy.
    * ``on_up`` and ``on_down`` fire exactly once per transition.
    * ``snapshot`` exposes state for observability/telemetry.
    """

    def __init__(
        self,
        fetcher: Any,
        *,
        interval_sec: float = 10.0,
        on_up: Callable[[dict[str, Any]], None] | None = None,
        on_down: Callable[[str], None] | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.interval = max(0.05, float(interval_sec))
        self.on_up = on_up
        self.on_down = on_down

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._is_up: bool | None = None
        self._last_ok_at: float | None = None
        self._last_err_at: float | None = None
        self._last_error: str | None = None
        self._fired_up = False
        self._fired_down = False

    # ------------------------------------------------------------------
    # lifecycle
    def start(self) -> None:
        """Start the watchdog thread if not already running."""

        with self._lock:
            if self._thread and self._thread.is_alive():  # already running
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="tws-watchdog",
                daemon=True,
            )
            self._thread.start()

    def stop(self, *, timeout: float | None = None) -> None:
        """Terminate the watchdog thread gracefully."""

        self._stop.set()
        thread = None
        with self._lock:
            thread = self._thread
        if thread:
            thread.join(timeout=timeout or (self.interval * 2))
        with self._lock:
            self._thread = None

    # ------------------------------------------------------------------
    # telemetry
    def snapshot(self) -> WatchdogSnapshot:
        with self._lock:
            state = "unknown" if self._is_up is None else ("up" if self._is_up else "down")
            return WatchdogSnapshot(
                up=self._is_up is True,
                state=state,
                last_ok_at=self._last_ok_at,
                last_err_at=self._last_err_at,
                last_error=self._last_error,
                interval_sec=self.interval,
            )

    # ------------------------------------------------------------------
    # worker
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                info = self.fetcher.handshake_test()
                ok = bool(info and info.get("handshake") == "ok")
            except Exception as exc:  # capture transient/network errors
                ok = False
                error_message = f"{type(exc).__name__}: {exc}"
                self._record_error(error_message)
                self._fire_on_down(error_message)
            else:
                if ok:
                    self._record_ok()
                    self._fire_on_up(info)  # info useful to callbacks
                else:
                    error_message = "handshake not ok"
                    self._record_error(error_message)
                    self._fire_on_down(error_message)
            finally:
                # Respect the interval but allow prompt shutdown
                self._stop.wait(self.interval)

    # ------------------------------------------------------------------
    # state helpers (callers already handle locks)
    def _record_ok(self) -> None:
        now = time.time()
        with self._lock:
            was_up = self._is_up is True
            self._is_up = True
            self._last_ok_at = now
            if not was_up:
                self._last_error = None
                self._fired_up = False
                self._fired_down = False

    def _record_error(self, message: str) -> None:
        now = time.time()
        with self._lock:
            was_down = self._is_up is False
            self._last_err_at = now
            self._last_error = message
            self._is_up = False
            if not was_down:
                self._fired_down = False
                self._fired_up = False

    def _fire_on_up(self, info: dict[str, Any]) -> None:
        if not self.on_up:
            return
        with self._lock:
            should_fire = self._is_up is True and not self._fired_up
            self._fired_up = True
            self._fired_down = False
        if should_fire:
            try:
                self.on_up(info)
            except Exception:
                # Avoid crashing the watchdog; surface via stderr tracebacks
                import traceback

                traceback.print_exc()

    def _fire_on_down(self, message: str) -> None:
        if not self.on_down:
            return
        with self._lock:
            should_fire = self._is_up is False and not self._fired_down
            self._fired_down = True
            self._fired_up = False
        if should_fire:
            try:
                self.on_down(message)
            except Exception:
                import traceback

                traceback.print_exc()
