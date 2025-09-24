from __future__ import annotations

from typing import Any

# Sentinel default values used to coerce raw snapshots into numeric form.
# Exposed via ``tws_translator`` for backwards compatibility with older
# provider wiring (see ``test_ibkr_coverage.py``).


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


def tws_translator(raw: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Compatibility wrapper expected by legacy coverage tests.

    Historically ``TwsFeaturesProvider`` was constructed with a ``tws_translator``
    callable. The modern implementation exposes ``translate_snapshots`` instead,
    but the older name survives in a few scripts (notably ``test_ibkr_coverage``).
    Providing this thin wrapper lets those entry points keep working while we
    continue steering new code toward ``translate_snapshots``.
    """

    return translate_snapshots(raw)
