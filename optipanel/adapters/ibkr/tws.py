from __future__ import annotations

from collections.abc import Callable
from typing import Any

_REQUIRED = ("last", "dma20", "support", "resistance", "rvol", "rs_strength", "vwap_diff")


def _sanitize_feature_map(m: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in _REQUIRED:
        v = m.get(k, 0.0)
        try:
            out[k] = float(v)
        except Exception:
            out[k] = 0.0
    return out


class TwsFeaturesProvider:
    """
    IBKR TWS/IBGW features provider.

    This class is intentionally dependency-free and *injectable* so tests remain pure:
      - fetcher(symbols) -> raw snapshot(s) (whatever shape your TWS client returns)
      - translator(raw)  -> {symbol: {last, dma20, support, resistance, rvol, rs_strength, vwap_diff}}

    Later, you can pass a real fetcher that uses ibapi or Web API. For now we pass a mock.
    """

    def __init__(
        self,
        fetcher: Callable[[list[str]], Any],
        translator: Callable[[Any], dict[str, dict[str, Any]]],
    ) -> None:
        self._fetcher = fetcher
        self._translator = translator

    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        raw = self._fetcher(list(symbols))
        feats = self._translator(raw) or {}
        out: dict[str, dict[str, float]] = {}
        for s in symbols:
            out[s] = _sanitize_feature_map(feats.get(s, {}))
        return out
