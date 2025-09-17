from __future__ import annotations
from typing import Dict, Any

def translate_snapshots(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Convert TWS-like raw snapshots into our normalized features:
      last, dma20, support, resistance, rvol, rs_strength, vwap_diff

    Expected raw shape per symbol (examples in tests):
    {
      "last": 105.12,
      "ma20": 100.01,                     # or "dma20"
      "levels": {"support": 101, "resistance": 106},
      "vwap": 103.8,
      "intraday": {"vol": 1_200_000, "baseline": 1_000_000},  # volume so far vs expected by now
      "rs": {"ref": "SPY", "sym_ret": 0.008, "ref_ret": -0.002}
    }
    """
    out: Dict[str, Dict[str, float]] = {}
    for sym, r in (raw or {}).items():
        try:
            last = float(r.get("last", 0.0))
        except Exception:
            last = 0.0

        # dma20 from explicit field or MA20
        try:
            dma20 = float(r.get("dma20", r.get("ma20", 0.0)))
        except Exception:
            dma20 = 0.0

        lv = r.get("levels", {}) or {}
        try:
            support = float(lv.get("support", r.get("support", 0.0)))
        except Exception:
            support = 0.0
        try:
            resistance = float(lv.get("resistance", r.get("resistance", 0.0)))
        except Exception:
            resistance = 0.0

        try:
            vwap = float(r.get("vwap", 0.0))
        except Exception:
            vwap = 0.0

        intr = r.get("intraday", {}) or {}
        try:
            vol = float(intr.get("vol", 0.0))
        except Exception:
            vol = 0.0
        try:
            base = float(intr.get("baseline", 0.0))
        except Exception:
            base = 0.0
        rvol = (vol / base) if base > 0 else 0.0

        rs = r.get("rs", {}) or {}
        try:
            sym_ret = float(rs.get("sym_ret", 0.0))
        except Exception:
            sym_ret = 0.0
        try:
            ref_ret = float(rs.get("ref_ret", 0.0))
        except Exception:
            ref_ret = 0.0
        rs_strength = sym_ret - ref_ret

        vwap_diff = ((last - vwap) / vwap) if vwap > 0 else 0.0

        out[sym] = {
            "last": last,
            "dma20": dma20,
            "support": support,
            "resistance": resistance,
            "rvol": rvol,
            "rs_strength": rs_strength,
            "vwap_diff": vwap_diff,
        }
    return out
