from __future__ import annotations

from typing import Any


def _as_float(v: Any, default: float) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def translate_snapshots(raw: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    """
    Convert raw snapshots into feature dicts with safe numeric types.
    If input already looks like features, this preserves values
    (aside from numeric coercion) so 'direct' vs 'via' paths match.
    """
    out: dict[str, dict[str, float]] = {}
    for sym, snap in (raw or {}).items():
        d = snap if isinstance(snap, dict) else {}
        out[sym] = {
            "last": _as_float(d.get("last"), 0.0),
            "dma20": _as_float(d.get("dma20"), 0.0),
            "support": _as_float(d.get("support"), 0.0),
            "resistance": _as_float(d.get("resistance"), 0.0),
            "rvol": _as_float(d.get("rvol"), 1.0),
            "rs_strength": _as_float(d.get("rs_strength"), 0.0),
            "vwap_diff": _as_float(d.get("vwap_diff"), 0.0),
        }
    return out
