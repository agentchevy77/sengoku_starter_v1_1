from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import threading, time, math
from datetime import datetime, time as dtime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # Python <3.9 fallback not needed here

# Lazy import ibapi so core tests don't require it
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import BarData
except Exception:  # pragma: no cover
    EClient = EWrapper = Contract = BarData = None  # type: ignore


def _est_now():
    tz = ZoneInfo("America/New_York") if ZoneInfo else timezone(timedelta(hours=-5))
    return datetime.now(tz)

def _rth_progress(now: Optional[datetime] = None) -> float:
    """Return fraction of regular session elapsed (09:30–16:00 ET)."""
    now = now or _est_now()
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end   = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now <= start: return 0.0
    if now >= end:   return 1.0
    return (now - start).total_seconds() / (end - start).total_seconds()

def _build_stock(symbol: str, primary: Optional[str] = None) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    if primary:
        c.primaryExchange = primary
    return c

def _pivot_levels(prev_high: float, prev_low: float, prev_close: float) -> Tuple[float, float]:
    """Classic floor pivots S1/R1."""
    p = (prev_high + prev_low + prev_close) / 3.0
    r1 = 2 * p - prev_low
    s1 = 2 * p - prev_high
    return s1, r1


# -------------- Minimal synchronous historical client --------------

class _IBApp(EWrapper, EClient):  # type: ignore[misc]
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)

        self._next_valid_id = None
        self._next_valid_id_event = threading.Event()

        self.hist_data: Dict[int, List[BarData]] = {}
        self.hist_done: Dict[int, threading.Event] = {}
        self.errors: List[Tuple[int,int,str]] = []

    # connection / ids
    def nextValidId(self, orderId: int):
        self._next_valid_id = orderId
        self._next_valid_id_event.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        # collect; IB sends benign 'data farm connection is OK' with -1
        self.errors.append((int(reqId or -1), int(errorCode or -1), str(errorString or "")))

    # historical bars
    def historicalData(self, reqId: int, bar: BarData):
        self.hist_data.setdefault(reqId, []).append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        ev = self.hist_done.get(reqId)
        if ev:
            ev.set()


@dataclass
class RealTwsFetcherConfig:
    host: str = "127.0.0.1"
    port: int = 7497          # TWS paper default
    client_id: int = 107
    ref_symbol: str = "SPY"   # for RS strength baselining
    useRTH: int = 1           # 1=regular session bars only
    intraday_bar: str = "5 mins"
    intraday_duration: str = "1 D"
    daily_duration: str = "30 D"
    daily_bar: str = "1 day"
    whatToShow: str = "TRADES"
    connect_timeout_sec: float = 5.0
    request_timeout_sec: float = 10.0


class RealTwsFetcher:
    """
    Synchronous fetcher that gathers:
      - intraday bars (VWAP, intraday volume, last)
      - 20D daily bars (DMA20, avg daily volume)
      - previous day H/L/C for pivot S1/R1
      - reference (e.g., SPY) last vs prev close to compute RS

    Returns a TWS-like 'raw' dict per symbol:
      {
        "last": ..., "ma20": ...,
        "levels": {"support": S1, "resistance": R1},
        "vwap": ...,
        "intraday": {"vol": vol_so_far, "baseline": exp_vol_by_now},
        "rs": {"ref":"SPY", "sym_ret": symRet, "ref_ret": refRet}
      }
    """
    def __init__(self, cfg: RealTwsFetcherConfig):
        if EClient is None:  # pragma: no cover
            raise ImportError("ibapi not installed. Activate venv then: pip install 'ibapi>=10.19.1'")
        self.cfg = cfg

    def __call__(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        app = _IBApp()
        app.connect(self.cfg.host, int(self.cfg.port), int(self.cfg.client_id))
        t0 = time.time()
        while not app._next_valid_id_event.is_set():
            if time.time() - t0 > self.cfg.connect_timeout_sec:
                app.disconnect()
                raise TimeoutError("TWS connect timeout—check TWS API settings (Enable API, port, client id).")
            time.sleep(0.05)

        # Helper: synchronous historical request
        def get_hist(contract: Contract, end: str, duration: str, bar: str, what: str, useRTH: int) -> List[BarData]:
            reqId = getattr(get_hist, "_rid", 9000)
            setattr(get_hist, "_rid", reqId + 1)
            app.hist_done[reqId] = threading.Event()
            app.reqHistoricalData(
                reqId, contract, endDateTime=end, durationStr=duration,
                barSizeSetting=bar, whatToShow=what, useRTH=useRTH, formatDate=1, keepUpToDate=False, chartOptions=[]
            )
            ev = app.hist_done[reqId]
            if not ev.wait(self.cfg.request_timeout_sec):
                raise TimeoutError(f"HistoricalData timeout for {contract.symbol} {duration} {bar}")
            bars = app.hist_data.get(reqId, [])[:]
            # Always cancel to be safe
            try:
                app.cancelHistoricalData(reqId)
            except Exception:
                pass
            return bars

        refC = _build_stock(self.cfg.ref_symbol)
        # Reference daily (for RS)
        ref_daily = get_hist(refC, end="", duration=self.cfg.daily_duration, bar=self.cfg.daily_bar,
                             what=self.cfg.whatToShow, useRTH=self.cfg.useRTH)
        if len(ref_daily) < 2:
            raise RuntimeError("Not enough reference bars for RS. Check market data permissions.")

        ref_last = float(ref_daily[-1].close)
        ref_prev_close = float(ref_daily[-2].close)
        ref_ret = (ref_last / ref_prev_close - 1.0) if ref_prev_close > 0 else 0.0

        out: Dict[str, Dict[str, Any]] = {}

        for sym in symbols:
            c = _build_stock(sym)
            # Intraday bars for VWAP/vol/last
            intra = get_hist(c, end="", duration=self.cfg.intraday_duration, bar=self.cfg.intraday_bar,
                             what=self.cfg.whatToShow, useRTH=self.cfg.useRTH)
            # Daily bars for DMA20 and pivots
            daily = get_hist(c, end="", duration=self.cfg.daily_duration, bar=self.cfg.daily_bar,
                             what=self.cfg.whatToShow, useRTH=self.cfg.useRTH)

            if not intra or len(daily) < 2:
                # still return a minimal structure; translator will sanitize
                out[sym] = {"last": 0.0, "ma20": 0.0, "levels": {"support": 0.0, "resistance": 0.0},
                            "vwap": 0.0, "intraday": {"vol": 0.0, "baseline": 0.0},
                            "rs": {"ref": self.cfg.ref_symbol, "sym_ret": 0.0, "ref_ret": ref_ret}}
                continue

            # ----- intraday aggregates -----
            # IB returns bars with date like "20250916" for daily and "20250916 15:05:00" for intraday
            today = _est_now().date()
            def _is_today(b: BarData) -> bool:
                d = str(getattr(b, "date"))
                return d.startswith(today.strftime("%Y%m%d"))

            todays = [b for b in intra if _is_today(b)]
            if not todays:
                todays = intra[-min(len(intra), 78):]  # fallback: last ~6.5h of 5-min bars

            vol_so_far = sum(float(b.volume) for b in todays)
            vwap_num = sum(float(b.close) * float(b.volume) for b in todays)
            vwap_den = vol_so_far if vol_so_far > 0 else 1.0
            vwap = vwap_num / vwap_den
            last = float(todays[-1].close)

            # ----- daily aggregates -----
            closes = [float(b.close) for b in daily[-20:]]
            dma20 = sum(closes) / len(closes) if closes else 0.0
            avg_vol20 = sum(float(b.volume) for b in daily[-20:]) / (len(daily[-20:]) or 1)

            prev = daily[-2]
            prev_high, prev_low, prev_close = float(prev.high), float(prev.low), float(prev.close)
            s1, r1 = _pivot_levels(prev_high, prev_low, prev_close)

            # ----- relative volume baseline (time-adjusted) -----
            progress = _rth_progress()
            baseline = avg_vol20 * max(0.05, min(1.0, progress))  # clamp small floor

            # ----- RS strength (since prev close) -----
            sym_prev_close = float(daily[-2].close)
            sym_ret = (last / sym_prev_close - 1.0) if sym_prev_close > 0 else 0.0

            out[sym] = {
                "last": last,
                "ma20": dma20,
                "levels": {"support": s1, "resistance": r1},
                "vwap": vwap,
                "intraday": {"vol": vol_so_far, "baseline": baseline},
                "rs": {"ref": self.cfg.ref_symbol, "sym_ret": sym_ret, "ref_ret": ref_ret},
            }

        app.disconnect()
        return out
