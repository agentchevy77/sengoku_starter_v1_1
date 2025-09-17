from __future__ import annotations
from typing import Dict, Any, List, Callable

def _as_float(v: Any, default: float) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _sanitize_features(raw: Dict[str, Any]) -> Dict[str, float]:
    """Always ensure features are properly typed."""
    return {
        "last":        _as_float(raw.get("last"),        0.0),
        "dma20":       _as_float(raw.get("dma20"),       0.0),
        "support":     _as_float(raw.get("support"),     0.0),
        "resistance":  _as_float(raw.get("resistance"),  0.0),
        "rvol":        _as_float(raw.get("rvol"),        1.0),
        "rs_strength": _as_float(raw.get("rs_strength"), 0.0),
        "vwap_diff":   _as_float(raw.get("vwap_diff"),   0.0),
    }

class TwsFeaturesProvider:
    """
    Small façade that takes a fetcher (callable: symbols -> raw snapshots)
    and a translator (callable: raw -> features), and exposes a single
    features_for_symbols(symbols) method used by the runtime.
    """
    def __init__(self, fetcher, translator: Callable[[Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Any]]]):
        self.fetcher = fetcher
        self.translator = translator

    def features_for_symbols(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        raw = self.fetcher(symbols)
        translated = self.translator(raw)
        # Always sanitize, even if translator is "identity"
        sanitized = {}
        for sym, data in translated.items():
            if isinstance(data, dict):
                sanitized[sym] = _sanitize_features(data)
            else:
                sanitized[sym] = _sanitize_features({})
        return sanitized
