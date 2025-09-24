import dataclasses
import threading
from types import SimpleNamespace

import pytest

import optipanel.adapters.ibkr.tws_fetcher as tws_mod
from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, TwsConfig


def _bars_from_closes(closes: list[float]) -> list[tuple[str, float, float, float, float, int]]:
    bars: list[tuple[str, float, float, float, float, int]] = []
    for idx, close in enumerate(closes, start=1):
        date = f"2024-01-{idx:02d}"
        high = close + 0.8
        low = close - 0.7
        open_px = close - 0.3
        bars.append((date, open_px, high, low, close, 1_000 + idx))
    return bars


class FakeHistSession:
    """Minimal replacement for _HistApp used in unit tests."""

    def __init__(self, symbol_to_bars: dict[str, list[tuple[str, float, float, float, float, int]]]):
        self._symbol_to_bars = symbol_to_bars
        self.ready = threading.Event()
        self.ready.set()
        self._events: dict[int, threading.Event] = {}
        self._pending: dict[int, list[tuple[str, float, float, float, float, int]]] = {}
        self.requested_symbols: list[str] = []

    def register_request(self, req_id: int) -> threading.Event:
        evt = threading.Event()
        self._events[req_id] = evt
        return evt

    def reqHistoricalData(self, req_id: int, contract, *_, **__):  # noqa: N802 - mimic ibapi naming
        symbol = getattr(contract, "symbol", None) or getattr(contract, "localSymbol", "")
        bars = list(self._symbol_to_bars.get(symbol, []))
        self._pending[req_id] = bars
        self.requested_symbols.append(symbol)
        evt = self._events.get(req_id)
        if evt is not None:
            evt.set()

    def take_bars(self, req_id: int):
        return list(self._pending.pop(req_id, []))

    def release(self, req_id: int) -> None:
        self._events.pop(req_id, None)

    def disconnect(self) -> None:  # pragma: no cover - interface parity only
        pass


def _expected_features(closes: list[float], ref_closes: list[float]) -> dict[str, float]:
    last = closes[-1]
    window = closes[-20:] if len(closes) >= 20 else closes
    dma20 = sum(window) / len(window)
    support = min(window)
    resistance = max(window)
    ago = closes[-21] if len(closes) >= 21 else (closes[0] if closes else last)
    ref_ago = ref_closes[-21] if len(ref_closes) >= 21 else (ref_closes[0] if ref_closes else ref_closes[-1])
    sym_ret20 = (last / ago - 1.0) if ago else 0.0
    ref_ret20 = (ref_closes[-1] / ref_ago - 1.0) if ref_ago else 0.0
    rs_strength = sym_ret20 - ref_ret20
    return {
        "last": float(last),
        "dma20": float(dma20),
        "support": float(support),
        "resistance": float(resistance),
        "rs_strength": float(rs_strength),
    }


def _sequence(base: float, step: float) -> list[float]:
    return [base + step * idx for idx in range(30)]


@pytest.mark.unit
def test_features_for_symbols_with_fake_session(monkeypatch):
    ref_closes = _sequence(100.0, 1.0)
    aapl_closes = _sequence(150.0, 1.8)
    msft_closes = _sequence(90.0, 0.6)

    bars_map = {
        "SPY": _bars_from_closes(ref_closes),
        "AAPL": _bars_from_closes(aapl_closes),
        "MSFT": _bars_from_closes(msft_closes),
    }

    fake_session = FakeHistSession(bars_map)

    cfg = dataclasses.replace(
        TwsConfig(
            host="fake",
            port=4002,
            client_id=99,
            ref_symbol="SPY",
            handshake_timeout=0.1,
            hist_timeout=0.1,
            daily_ttl_sec=1.0,
            intraday_ttl_sec=1.0,
            pacing_interval_sec=0.1,
            pacing_max_requests=10,
            pacing_min_delay_sec=0.0,
            pacing_error_delay_sec=0.0,
            global_rate_max_requests=0,
            global_rate_interval_sec=1.0,
        )
    )
    fetcher = RealTwsFetcher(cfg)

    # Disable pacing to keep the test synchronous and deterministic.
    fetcher._global_rate_limiter._enabled = False
    fetcher._request_window.clear()

    monkeypatch.setattr(fetcher, "_connect", lambda: fake_session)
    monkeypatch.setattr(fetcher, "_pace_request", lambda: None)
    monkeypatch.setattr(tws_mod, "_stock_contract", lambda symbol: SimpleNamespace(symbol=symbol))

    result = fetcher.features_for_symbols(["AAPL", "MSFT"])

    assert set(result) == {"AAPL", "MSFT"}
    assert fake_session.requested_symbols == ["SPY", "AAPL", "MSFT"]

    expected_aapl = _expected_features(aapl_closes, ref_closes)
    data_aapl = result["AAPL"]
    assert data_aapl["last"] == pytest.approx(expected_aapl["last"], rel=1e-6)
    assert data_aapl["dma20"] == pytest.approx(expected_aapl["dma20"], rel=1e-6)
    assert data_aapl["support"] == pytest.approx(expected_aapl["support"], rel=1e-6)
    assert data_aapl["resistance"] == pytest.approx(expected_aapl["resistance"], rel=1e-6)
    assert data_aapl["rs_strength"] == pytest.approx(expected_aapl["rs_strength"], rel=1e-6)
    assert data_aapl["bundles"]["1d"]["last"] == pytest.approx(expected_aapl["last"], rel=1e-6)

    expected_msft = _expected_features(msft_closes, ref_closes)
    data_msft = result["MSFT"]
    assert data_msft["last"] == pytest.approx(expected_msft["last"], rel=1e-6)
    assert data_msft["support"] == pytest.approx(expected_msft["support"], rel=1e-6)
    assert data_msft["resistance"] == pytest.approx(expected_msft["resistance"], rel=1e-6)
    assert data_msft["rs_strength"] == pytest.approx(expected_msft["rs_strength"], rel=1e-6)

    for payload in result.values():
        assert payload["rvol"] == pytest.approx(1.0)
        assert payload["vwap_diff"] == pytest.approx(0.0)
