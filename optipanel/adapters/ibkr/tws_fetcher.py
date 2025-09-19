from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


@dataclass(frozen=True)
class TwsConfig:
    host: str = os.getenv("SENGOKU_TWS_HOST", "127.0.0.1")
    port: int = int(os.getenv("SENGOKU_TWS_PORT", "7496"))
    client_id: int = int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107"))
    ref_symbol: str | None = os.getenv("SENGOKU_TWS_REF", "SPY")

    # timeouts
    handshake_timeout: float = float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0"))
    hist_timeout: float = float(os.getenv("SENGOKU_TWS_HIST_TIMEOUT", "15.0"))

    # caching (seconds)
    daily_ttl_sec: float = float(os.getenv("SENGOKU_TWS_DAILY_TTL", str(23 * 60 * 60)))  # off-hours
    intraday_ttl_sec: float = float(os.getenv("SENGOKU_TWS_INTRADAY_TTL", "300"))  # during market
    dynamic_ttl: bool = bool(int(os.getenv("SENGOKU_TWS_DYNAMIC_TTL", "1")))
    stale_ok_sec: float = float(os.getenv("SENGOKU_TWS_STALE_OK", "900"))  # fallback window

    # cache size
    daily_max_entries: int = int(os.getenv("SENGOKU_TWS_DAILY_MAX_ENTRIES", "100"))

    # pacing
    pacing_interval_sec: float = float(os.getenv("SENGOKU_TWS_PACING_INTERVAL", "5.0"))
    pacing_max_requests: int = int(os.getenv("SENGOKU_TWS_PACING_MAX_REQS", "40"))
    pacing_min_delay_sec: float = float(os.getenv("SENGOKU_TWS_PACING_MIN_DELAY", "0.2"))
    pacing_error_delay_sec: float = float(os.getenv("SENGOKU_TWS_PACING_ERROR_DELAY", "2.0"))


def cfg_from_env() -> TwsConfig:
    return TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107")),
        ref_symbol=os.getenv("SENGOKU_TWS_REF", "SPY"),
        handshake_timeout=float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0")),
        hist_timeout=float(os.getenv("SENGOKU_TWS_HIST_TIMEOUT", "15.0")),
        daily_ttl_sec=float(os.getenv("SENGOKU_TWS_DAILY_TTL", str(23 * 60 * 60))),
        intraday_ttl_sec=float(os.getenv("SENGOKU_TWS_INTRADAY_TTL", "300")),
        dynamic_ttl=bool(int(os.getenv("SENGOKU_TWS_DYNAMIC_TTL", "1"))),
        stale_ok_sec=float(os.getenv("SENGOKU_TWS_STALE_OK", "900")),
        daily_max_entries=int(os.getenv("SENGOKU_TWS_DAILY_MAX_ENTRIES", "100")),
        pacing_interval_sec=float(os.getenv("SENGOKU_TWS_PACING_INTERVAL", "5.0")),
        pacing_max_requests=int(os.getenv("SENGOKU_TWS_PACING_MAX_REQS", "40")),
        pacing_min_delay_sec=float(os.getenv("SENGOKU_TWS_PACING_MIN_DELAY", "0.2")),
        pacing_error_delay_sec=float(os.getenv("SENGOKU_TWS_PACING_ERROR_DELAY", "2.0")),
    )


class _BaseApp(EWrapper, EClient):
    _NON_FATAL = {2104, 2106, 2158}

    def __init__(self):
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.errors: list[tuple[int, str]] = []

    def error(self, reqId, code, msg, advancedOrderRejectJson=""):
        if code not in self._NON_FATAL:
            self.errors.append((code, str(msg)))

    def nextValidId(self, orderId):
        self.ready.set()


class _HistApp(_BaseApp):
    def __init__(self):
        super().__init__()
        self._bars: dict[int, list[tuple[str, float, float, float, float, int]]] = {}
        self._done: dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    # ibapi BarData: date, open, high, low, close, volume, average, barCount
    def historicalData(self, reqId, bar):
        with self._lock:
            self._bars.setdefault(reqId, []).append(
                (str(bar.date), float(bar.open), float(bar.high), float(bar.low), float(bar.close), int(bar.volume))
            )

    def historicalDataEnd(self, reqId, start, end):
        with self._lock:
            self._done.setdefault(reqId, threading.Event()).set()


def _stock_contract(symbol: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.exchange = "SMART"
    c.currency = "USD"
    return c


class RealTwsFetcher:
    """Real TWS fetcher: stable handshake + minimal daily-bars features with LRU cache and dynamic TTL."""

    def __init__(self, cfg: TwsConfig | None = None):
        self.cfg = cfg or cfg_from_env()
        self._req_id = 1000
        # LRU: maps symbol -> (last_access_ts, bars)
        self._daily_cache: OrderedDict[str, tuple[float, list[tuple[str, float, float, float, float, int]]]] = (
            OrderedDict()
        )
        self._last_ok: float = 0.0
        self._last_error: str | None = None
        self._request_window: deque[float] = deque()
        self._last_request_ts: float = 0.0
        self._last_latency: float = 0.0
        self._fresh_requests: int = 0

    # ---------- time / ttl helpers ----------
    def _current_ttl(self) -> float:
        if not self.cfg.dynamic_ttl:
            return self.cfg.daily_ttl_sec
        # naive local time check; good enough for our use
        t = time.localtime()
        # treat 09:00–15:59 as "market hours"; tune via env if needed
        intraday = 9 <= t.tm_hour < 16
        return self.cfg.intraday_ttl_sec if intraday else self.cfg.daily_ttl_sec

    # ---------- pacing helpers ----------
    def _pace_request(self) -> None:
        now = time.time()
        interval = max(0.0, float(self.cfg.pacing_interval_sec))
        max_reqs = max(0, int(self.cfg.pacing_max_requests))
        min_delay = max(0.0, float(self.cfg.pacing_min_delay_sec))

        # respect minimum spacing between consecutive requests
        if self._last_request_ts and min_delay > 0:
            elapsed = now - self._last_request_ts
            if elapsed < min_delay:
                sleep_for = min_delay - elapsed
                logger.debug("TWS pacing: sleeping %.3fs to respect min delay", sleep_for)
                time.sleep(sleep_for)
                now = time.time()

        if interval > 0 and max_reqs > 0:
            window = self._request_window
            while window and (now - window[0]) > interval:
                window.popleft()
            if len(window) >= max_reqs:
                sleep_for = interval - (now - window[0]) + 0.01
                if sleep_for > 0:
                    logger.debug("TWS pacing: sleeping %.3fs (requests=%d limit=%d)", sleep_for, len(window), max_reqs)
                    time.sleep(sleep_for)
                    now = time.time()
                    while window and (now - window[0]) > interval:
                        window.popleft()

        self._last_request_ts = time.time()
        self._request_window.append(self._last_request_ts)
        self._fresh_requests += 1

    # ---------- connectivity ----------
    def _connect(self) -> _HistApp:
        app = _HistApp()
        app.connect(self.cfg.host, self.cfg.port, clientId=self.cfg.client_id)
        t = threading.Thread(target=app.run, name="tws-run", daemon=True)
        t.start()
        if not app.ready.wait(self.cfg.handshake_timeout):
            app.disconnect()
            self._last_error = f"handshake timeout host={self.cfg.host} port={self.cfg.port} id={self.cfg.client_id}"
            raise TimeoutError(self._last_error)
        self._last_ok = time.time()
        self._last_error = None
        return app

    def handshake_test(self) -> dict[str, Any]:
        app = self._connect()
        try:
            return {
                "host": self.cfg.host,
                "port": self.cfg.port,
                "client_id": self.cfg.client_id,
                "handshake": "ok",
                "errors": app.errors,
                "last_ok": self._last_ok,
            }
        finally:
            app.disconnect()

    # ---------- daily bars (LRU + dynamic TTL) ----------
    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _prune_daily_cache(self) -> None:
        limit = max(1, int(self.cfg.daily_max_entries))
        while len(self._daily_cache) > limit:
            self._daily_cache.popitem(last=False)  # pop LRU

    def _get_cached(
        self, symbol: str, now: float, allow_stale: bool
    ) -> list[tuple[str, float, float, float, float, int]] | None:
        ent = self._daily_cache.get(symbol)
        if not ent:
            return None
        ts, bars = ent
        age = now - ts
        ttl = self._current_ttl()
        if age < ttl or (allow_stale and age < self.cfg.stale_ok_sec):
            # refresh access timestamp and move to MRU
            self._daily_cache[symbol] = (now, bars)
            self._daily_cache.move_to_end(symbol, last=True)
            return bars
        return None

    def _fetch_daily(
        self, app: _HistApp, symbol: str, days: int = 30
    ) -> list[tuple[str, float, float, float, float, int]]:
        now = time.time()
        cached = self._get_cached(symbol, now, allow_stale=False)
        if cached is not None:
            return cached

        req_id = self._next_id()
        app._done[req_id] = threading.Event()
        app.reqHistoricalData(
            req_id,
            _stock_contract(symbol),
            endDateTime="",
            durationStr=f"{days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )

        try:
            if not app._done[req_id].wait(self.cfg.hist_timeout):
                # try stale fallback
                stale = self._get_cached(symbol, now, allow_stale=True)
                if stale is not None:
                    return stale
                raise TimeoutError(f"historicalData timeout for {symbol}")

            bars = list(app._bars.get(req_id, []))
        finally:
            # Always release per-request registries to avoid unbounded growth in long-lived sessions.
            app._bars.pop(req_id, None)
            done_evt = app._done.pop(req_id, None)
            if done_evt is not None:
                done_evt.set()

        # store/update LRU
        self._daily_cache[symbol] = (now, bars)
        self._daily_cache.move_to_end(symbol, last=True)
        self._prune_daily_cache()
        return bars

    # ---------- public API ----------
    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        syms = list(dict.fromkeys(symbols))
        ref = (self.cfg.ref_symbol or os.getenv("SENGOKU_TWS_REF", "SPY")) or "SPY"
        all_syms = [ref] + [s for s in syms if s != ref]

        app = self._connect()
        try:
            daily: dict[str, list[tuple[str, float, float, float, float, int]]] = {}
            fresh_requests_start = self._fresh_requests
            for s in all_syms:
                self._pace_request()
                started = time.perf_counter()
                try:
                    daily[s] = self._fetch_daily(app, s, days=30)
                    self._last_latency = time.perf_counter() - started
                except Exception as exc:
                    logger.warning("TWS daily fetch failed for %s: %s", s, exc)
                    # last-ditch stale fallback
                    fallback = self._get_cached(s, time.time(), allow_stale=True)
                    daily[s] = fallback if fallback is not None else []
                    if self.cfg.pacing_error_delay_sec > 0:
                        logger.debug("TWS pacing: sleeping %.3fs after error", self.cfg.pacing_error_delay_sec)
                        time.sleep(self.cfg.pacing_error_delay_sec)
            fresh_requests = self._fresh_requests - fresh_requests_start
            if fresh_requests:
                logger.info(
                    "TWS pacing metrics: fresh_requests=%d window=%d interval=%.1fs last_latency=%.3fs",
                    fresh_requests,
                    len(self._request_window),
                    self.cfg.pacing_interval_sec,
                    self._last_latency,
                )
            # compute ref return
            ref_bars = daily.get(ref, [])
            ref_close = ref_bars[-1][4] if ref_bars else None
            ref_ago = ref_bars[-21][4] if len(ref_bars) >= 21 else None
            ref_ret20 = (ref_close / ref_ago - 1.0) if (ref_close and ref_ago and ref_ago != 0) else 0.0

            out: dict[str, dict[str, Any]] = {}
            for s in syms:
                bars = daily.get(s, [])
                closes = [b[4] for b in bars if b]
                if not closes:
                    out[s] = {
                        "last": 0.0,
                        "dma20": 0.0,
                        "support": 0.0,
                        "resistance": 0.0,
                        "rvol": 1.0,
                        "rs_strength": 0.0,
                        "vwap_diff": 0.0,
                    }
                    continue

                last = closes[-1]
                window = closes[-20:] if len(closes) >= 20 else closes
                dma20 = sum(window) / len(window)
                support = min(window)
                resistance = max(window)

                ago = closes[-21] if len(closes) >= 21 else (closes[0] if closes else last)
                sym_ret20 = (last / ago - 1.0) if (ago and ago != 0) else 0.0
                rs_strength = sym_ret20 - ref_ret20

                out[s] = {
                    "last": float(last),
                    "dma20": float(dma20),
                    "support": float(support),
                    "resistance": float(resistance),
                    "rvol": 1.0,
                    "rs_strength": float(rs_strength),
                    "vwap_diff": 0.0,
                }
            return out
        finally:
            app.disconnect()

    # legacy callable form
    def __call__(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return self.features_for_symbols(symbols)

    def pacing_metrics(self) -> dict[str, Any]:
        return {
            "requests_in_window": len(self._request_window),
            "window_interval_sec": self.cfg.pacing_interval_sec,
            "last_request_latency_sec": self._last_latency,
            "total_requests": self._fresh_requests,
        }


# Back-compat alias expected by CLI
RealTwsFetcherConfig = TwsConfig
