from __future__ import annotations
import os, threading, time
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract


@dataclass(frozen=True)
class TwsConfig:
    host: str = os.getenv("SENGOKU_TWS_HOST", "127.0.0.1")
    port: int = int(os.getenv("SENGOKU_TWS_PORT", "7496"))
    client_id: int = int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107"))
    handshake_timeout: float = float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0"))
    hist_timeout: float = float(os.getenv("SENGOKU_TWS_HIST_TIMEOUT", "15.0"))


def cfg_from_env() -> TwsConfig:
    return TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107")),
        handshake_timeout=float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0")),
        hist_timeout=float(os.getenv("SENGOKU_TWS_HIST_TIMEOUT", "15.0")),
    )


class _BaseApp(EWrapper, EClient):
    _NON_FATAL = {2104, 2106, 2158}
    def __init__(self):
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.errors: List[Tuple[int,str]] = []

    def error(self, reqId, code, msg, advancedOrderRejectJson=""):
        if code not in self._NON_FATAL:
            self.errors.append((code, str(msg)))

    def nextValidId(self, orderId):
        self.ready.set()


class _HistApp(_BaseApp):
    def __init__(self):
        super().__init__()
        self._bars: Dict[int, List[Tuple[str,float,float,float,float,int]]] = {}
        self._done: Dict[int, threading.Event] = {}
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
    """Real TWS fetcher: stable handshake + minimal daily-bars features."""
    def __init__(self, cfg: Optional[TwsConfig] = None):
        self.cfg = cfg or cfg_from_env()
        self._req_id = 1000  # our own request id counter

    # ---------- connectivity ----------
    def _connect(self) -> _HistApp:
        app = _HistApp()
        app.connect(self.cfg.host, self.cfg.port, clientId=self.cfg.client_id)
        t = threading.Thread(target=app.run, name="tws-run", daemon=True)
        t.start()
        if not app.ready.wait(self.cfg.handshake_timeout):
            app.disconnect()
            raise TimeoutError(f"TWS handshake timed out (host={self.cfg.host} port={self.cfg.port} id={self.cfg.client_id}).")
        return app

    def handshake_test(self) -> Dict[str, Any]:
        app = self._connect()
        try:
            return {"host": self.cfg.host, "port": self.cfg.port, "client_id": self.cfg.client_id, "handshake": "ok", "errors": app.errors}
        finally:
            app.disconnect()

    # ---------- historical daily helper ----------
    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _fetch_daily(self, app: _HistApp, symbol: str, days: int = 30) -> List[Tuple[str,float,float,float,float,int]]:
        reqId = self._next_id()
        app._done[reqId] = threading.Event()
        app.reqHistoricalData(
            reqId,
            _stock_contract(symbol),
            endDateTime="",
            durationStr=f"{days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]
        )
        if not app._done[reqId].wait(self.cfg.hist_timeout):
            raise TimeoutError(f"historicalData timeout for {symbol}")
        return app._bars.get(reqId, [])

    # ---------- public APIs ----------
    def features_for_symbols(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return features dict per symbol: last, dma20, support, resistance, rvol(=1.0), rs_strength, vwap_diff(=0.0)"""
        syms = list(dict.fromkeys(symbols))  # stable unique
        ref = os.getenv("SENGOKU_TWS_REF", "SPY")
        all_syms = [ref] + [s for s in syms if s != ref]

        app = self._connect()
        try:
            daily: Dict[str, List[Tuple[str,float,float,float,float,int]]] = {}
            for s in all_syms:
                try:
                    daily[s] = self._fetch_daily(app, s, days=30)
                    # Be polite: tiny gap to avoid pacing spikes (not strictly required for daily)
                    time.sleep(0.2)
                except Exception as e:
                    daily[s] = []

            # compute ref return
            ref_bars = daily.get(ref, [])
            ref_close = ref_bars[-1][4] if ref_bars else None
            ref_ago   = ref_bars[-21][4] if len(ref_bars) >= 21 else None
            ref_ret20 = (ref_close/ref_ago - 1.0) if (ref_close and ref_ago and ref_ago != 0) else 0.0

            out: Dict[str, Dict[str, Any]] = {}
            for s in syms:
                bars = daily.get(s, [])
                closes = [b[4] for b in bars if b]
                if not closes:
                    # minimal safe defaults
                    out[s] = dict(last=0.0, dma20=0.0, support=0.0, resistance=0.0, rvol=1.0, rs_strength=0.0, vwap_diff=0.0)
                    continue

                last = closes[-1]
                window = closes[-20:] if len(closes) >= 20 else closes
                dma20 = sum(window)/len(window)
                support = min(window)
                resistance = max(window)

                ago = closes[-21] if len(closes) >= 21 else (closes[0] if closes else last)
                sym_ret20 = (last/ago - 1.0) if (ago and ago != 0) else 0.0
                rs_strength = sym_ret20 - ref_ret20

                out[s] = dict(
                    last=float(last),
                    dma20=float(dma20),
                    support=float(support),
                    resistance=float(resistance),
                    rvol=1.0,          # TODO: intraday relative volume
                    rs_strength=float(rs_strength),
                    vwap_diff=0.0      # TODO: intraday vwap vs last
                )
            return out
        finally:
            app.disconnect()

    # Keep the __call__ too (legacy); delegate to features to stay consistent
    def __call__(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        return self.features_for_symbols(symbols)


# Back-compat alias expected by CLI (old name)
RealTwsFetcherConfig = TwsConfig
