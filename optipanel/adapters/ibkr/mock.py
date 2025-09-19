from __future__ import annotations

from typing import Any


class MockFeaturesProvider:
    """
    Deterministic provider that returns a static features table you pass in.
    Used for tests and offline demos.
    """

    def __init__(self, table: dict[str, dict[str, Any]] | None = None):
        self._table: dict[str, dict[str, Any]] = dict(table or {})
        self._ticks = 0

    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        self._ticks += 1
        out: dict[str, dict[str, Any]] = {}
        for s in symbols:
            # copy to avoid caller mutating internal table
            out[s] = dict(self._table.get(s, {}))
        return out

    def set(self, symbol: str, features: dict[str, Any]) -> None:
        self._table[symbol] = dict(features)
