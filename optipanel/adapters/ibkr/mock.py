from __future__ import annotations
from typing import Dict, Any, List, Optional

class MockFeaturesProvider:
    """
    Deterministic provider that returns a static features table you pass in.
    Used for tests and offline demos.
    """
    def __init__(self, table: Optional[Dict[str, Dict[str, Any]]] = None):
        self._table: Dict[str, Dict[str, Any]] = dict(table or {})
        self._ticks = 0

    def features_for_symbols(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        self._ticks += 1
        out: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            # copy to avoid caller mutating internal table
            out[s] = dict(self._table.get(s, {}))
        return out

    def set(self, symbol: str, features: Dict[str, Any]) -> None:
        self._table[symbol] = dict(features)
