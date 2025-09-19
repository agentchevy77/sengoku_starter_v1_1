from __future__ import annotations

from typing import Any


def _as_float(v: Any, default: float) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class MockFeaturesProvider:
    """
    Test-friendly provider that accepts feature dicts directly.
    Maintains the historical one-argument constructor used by tests.
    """

    def __init__(self, data: dict[str, dict[str, Any]] | None = None):
        self._data: dict[str, dict[str, Any]] = dict(data or {})

    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for sym in symbols:
            src = self._data.get(sym, {})
            out[sym] = {
                "last": _as_float(src.get("last"), 0.0),
                "dma20": _as_float(src.get("dma20"), 0.0),
                "support": _as_float(src.get("support"), 0.0),
                "resistance": _as_float(src.get("resistance"), 0.0),
                "rvol": _as_float(src.get("rvol"), 1.0),
                "rs_strength": _as_float(src.get("rs_strength"), 0.0),
                "vwap_diff": _as_float(src.get("vwap_diff"), 0.0),
            }
        return out

    def update(self, new_data: dict[str, dict[str, Any]]) -> None:
        self._data.update(new_data)

    def set(self, symbol: str, features: dict[str, Any]) -> None:
        """Set features for a single symbol (used by tests)."""
        self._data[symbol] = features
