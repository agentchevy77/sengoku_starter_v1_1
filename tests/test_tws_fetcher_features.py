import dataclasses
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
        self.ready = SimpleNamespace(set=lambda: None, wait=lambda timeout=None: True)
        self._events: dict[int, SimpleNamespace] = {}
        self._pending: dict[int, list[tuple[str, float, float, float, float, int]]] = {}
        self.requested_symbols: list[str] = []

    def register_request(self, req_id: int):
        evt = SimpleNamespace(set=lambda: None, wait=lambda timeout=None: True)
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

    def cleanup(self) -> None:  # pragma: no cover - compatibility with RealTwsFetcher expectations
        self.disconnect()


def _format_expected(closes: list[float]) -> list[dict[str, float]]:
    bars = _bars_from_closes(closes)
    return [
        {"date": date, "o": open_px, "h": high, "l": low, "c": close, "v": volume}
        for date, open_px, high, low, close, volume in bars
    ]


def _sequence(base: float, step: float) -> list[float]:
    return [base + step * idx for idx in range(30)]


@pytest.mark.unit
def test_fetch_daily_bars_returns_formatted_ohlcv(monkeypatch):
    closes_aapl = _sequence(150.0, 1.5)
    closes_msft = _sequence(90.0, 0.75)

    bars_map = {
        "AAPL": _bars_from_closes(closes_aapl),
        "MSFT": _bars_from_closes(closes_msft),
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

    fetcher._global_rate_limiter._enabled = False  # type: ignore[attr-defined]
    fetcher._request_window.clear()

    monkeypatch.setattr(fetcher, "_connect", lambda: fake_session)
    monkeypatch.setattr(fetcher, "_pace_request", lambda: None)
    monkeypatch.setattr(tws_mod, "_stock_contract", lambda symbol: SimpleNamespace(symbol=symbol))

    result = fetcher.fetch_daily_bars(["AAPL", "MSFT"])

    assert set(result) == {"AAPL", "MSFT"}
    assert fake_session.requested_symbols == ["AAPL", "MSFT"]
    assert result["AAPL"]["bars"] == _format_expected(closes_aapl)
    assert result["MSFT"]["bars"] == _format_expected(closes_msft)


def test_features_for_symbols_alias(monkeypatch, caplog):
    bars_map = {"AAPL": _bars_from_closes([100.0, 101.0])}
    fake_session = FakeHistSession(bars_map)

    cfg = TwsConfig(host="fake", port=4002, client_id=99, ref_symbol="SPY", handshake_timeout=0.1, hist_timeout=0.1)
    fetcher = RealTwsFetcher(cfg)
    fetcher._global_rate_limiter._enabled = False  # type: ignore[attr-defined]
    fetcher._request_window.clear()

    monkeypatch.setattr(fetcher, "_connect", lambda: fake_session)
    monkeypatch.setattr(fetcher, "_pace_request", lambda: None)
    monkeypatch.setattr(tws_mod, "_stock_contract", lambda symbol: SimpleNamespace(symbol=symbol))

    with caplog.at_level("WARNING"):
        alias_result = fetcher.features_for_symbols(["AAPL"])
    assert any("deprecated" in record.message for record in caplog.records)

    direct_result = fetcher.fetch_daily_bars(["AAPL"])
    assert alias_result == direct_result
