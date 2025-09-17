from __future__ import annotations
from typing import Dict, Any, List

class MockTwsFetcher:
    """
    A callable that returns 'raw' TWS-like snapshots for requested symbols,
    derived from a provided features table (the same keys our engine uses).
    """
    def __init__(self, features_table: Dict[str, Dict[str, Any]], ref: str = "SPY"):
        self.table = {k: dict(v) for k, v in (features_table or {}).items()}
        self.ref = ref

    def __call__(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        raw: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            f = self.table.get(s, {})
            last = float(f.get("last", 0.0))
            dma20 = float(f.get("dma20", last))
            support = float(f.get("support", last * 0.98))
            resistance = float(f.get("resistance", last * 1.02))
            rvol = float(f.get("rvol", 1.0))
            rs_strength = float(f.get("rs_strength", 0.0))
            vwd = float(f.get("vwap_diff", 0.0))
            vwap = last / (1.0 + vwd) if (1.0 + vwd) != 0 else last
            vol = 1_000_000.0 * rvol
            baseline = 1_000_000.0
            # Model rs as sym_ret - ref_ret = rs_strength, with ref_ret=0
            sym_ret, ref_ret = rs_strength, 0.0
            raw[s] = {
                "last": last,
                "ma20": dma20,
                "levels": {"support": support, "resistance": resistance},
                "vwap": vwap,
                "intraday": {"vol": vol, "baseline": baseline},
                "rs": {"ref": self.ref, "sym_ret": sym_ret, "ref_ret": ref_ret},
            }
        return raw
