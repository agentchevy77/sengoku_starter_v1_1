from __future__ import annotations
from typing import Dict, Any, List

class MockTwsFetcher:
    """
    Test helper. Return exactly what you've seeded via __init__ for the requested symbols.
    Shape-agnostic: can be "raw" or already-feature-shaped; the translator decides.
    """
    def __init__(self, data: Dict[str, Dict[str, Any]] | None = None):
        self._data = data or {}

    def __call__(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            if s in self._data:
                out[s] = self._data[s]
        return out

    # Compatibility: if someone calls the fetcher directly for features, just return the same
    def features_for_symbols(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        return self.__call__(symbols)
