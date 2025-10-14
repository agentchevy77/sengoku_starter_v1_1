from __future__ import annotations

from typing import Any

from optipanel.runtime.driver import run_driver
from optipanel.ui.command_room import render_command_room


def _build_symbol_features(symbols: list[str], feats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s: dict(feats.get(s, {})) for s in symbols}


def run_profiles_offline(
    profiles_cfg: dict[str, Any], features_dict: dict[str, dict[str, Any]], ticks: int = 3
) -> dict[str, Any]:
    ui = profiles_cfg.get("ui", {})
    width = int(ui.get("width", 24))
    top_n = int(ui.get("top_n", 1))

    watchlists = profiles_cfg.get("watchlists", {})
    budgets = profiles_cfg.get("budgets", {})

    lists_out: dict[str, Any] = {}
    for name, symbols in (watchlists or {}).items():
        sym_feats = _build_symbol_features(list(symbols), features_dict)
        budget = dict(budgets.get(name, {}))
        drv = run_driver(sym_feats, budget, ticks=int(ticks))

        panels: list[str] = []
        last_advice_counts = None
        top_last: list[str] = []
        last_prob_chips: dict[str, Any] = {}
        for t in drv.get("ticks", []):
            if t.get("scanned") and t.get("run"):
                panels.append(render_command_room(t["run"], width=width, top_n=top_n))
                last_advice_counts = t["run"]["scan"].get("advice_counts", last_advice_counts)
                top_last = t["run"]["scan"].get("top", top_last)
                for snap in t["run"].get("scan", {}).get("results", []):
                    chips = snap.get("prob_chips")
                    if chips:
                        last_prob_chips[snap.get("symbol", "?")] = chips

        lists_out[name] = {
            "scanned_count": drv.get("scanned_count", 0),
            "backoff_ticks": drv.get("backoff_ticks", 0),
            "panels": panels,
            "advice_counts_last": last_advice_counts or {"attack": 0, "defend": 0, "standby": 0},
            "top_last": top_last,
            "prob_chips_last": last_prob_chips,
        }

    return {"lists": lists_out, "ticks": int(ticks)}
