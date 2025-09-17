from __future__ import annotations
from typing import Dict, Any, List
from optipanel.runtime.driver import run_driver
from optipanel.ui.command_room import render_command_room

def _build_symbol_features(symbols: List[str], feats: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {s: dict(feats.get(s, {})) for s in symbols}

def run_profiles_offline(profiles_cfg: Dict[str, Any],
                         features_dict: Dict[str, Dict[str, Any]],
                         ticks: int = 3) -> Dict[str, Any]:
    ui = profiles_cfg.get("ui", {})
    width = int(ui.get("width", 24))
    top_n = int(ui.get("top_n", 1))

    watchlists = profiles_cfg.get("watchlists", {})
    budgets    = profiles_cfg.get("budgets", {})

    lists_out: Dict[str, Any] = {}
    for name, symbols in (watchlists or {}).items():
        sym_feats = _build_symbol_features(list(symbols), features_dict)
        budget = dict(budgets.get(name, {}))
        drv = run_driver(sym_feats, budget, ticks=int(ticks))

        panels: List[str] = []
        last_advice_counts = None
        top_last: List[str] = []
        for t in drv.get("ticks", []):
            if t.get("scanned") and t.get("run"):
                panels.append(render_command_room(t["run"], width=width, top_n=top_n))
                last_advice_counts = t["run"]["scan"].get("advice_counts", last_advice_counts)
                top_last = t["run"]["scan"].get("top", top_last)

        lists_out[name] = {
            "scanned_count": drv.get("scanned_count", 0),
            "backoff_ticks": drv.get("backoff_ticks", 0),
            "panels": panels,
            "advice_counts_last": last_advice_counts or {"attack":0,"defend":0,"standby":0},
            "top_last": top_last
        }

    return {"lists": lists_out, "ticks": int(ticks)}
