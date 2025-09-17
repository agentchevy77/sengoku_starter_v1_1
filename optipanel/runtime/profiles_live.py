from __future__ import annotations
from typing import Dict, Any, List
from optipanel.runtime.driver import LocalBudget, _expand_usage
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room
from optipanel.notify.engine import aggregate_alerts

def run_profiles_with_provider(profiles_cfg: Dict[str, Any],
                               provider: Any,
                               ticks: int = 3) -> Dict[str, Any]:
    """
    Drive each watchlist through a budget/backoff loop.
    On scan ticks, fetch features from provider and run the pure decision loop,
    collect Command Room panels, and aggregate alerts for a notifications strip.
    """
    ui = profiles_cfg.get("ui", {})
    width = int(ui.get("width", 24))
    top_n = int(ui.get("top_n", 1))

    watchlists = profiles_cfg.get("watchlists", {})
    budgets    = profiles_cfg.get("budgets", {})

    lists_out: Dict[str, Any] = {}
    for name, symbols in (watchlists or {}).items():
        symbols = list(symbols or [])
        budget_cfg = dict(budgets.get(name, {}))
        soft_cap  = int(budget_cfg.get("soft_cap", 10))
        cooldown  = int(budget_cfg.get("cooldown", 2))
        stride    = int(budget_cfg.get("scan_stride_backoff", 2))
        usage_seq = _expand_usage(budget_cfg.get("used_lines", 0), max(1, int(ticks)))

        budget = LocalBudget(soft_cap=soft_cap, cooldown=cooldown)
        panels: List[str] = []
        provider_calls = 0
        last_advice_counts = None
        top_last: List[str] = []
        runs: List[Dict[str, Any]] = []

        for i in range(max(1, int(ticks))):
            used = int(usage_seq[i])
            in_backoff = budget.step(used)
            do_scan = (i % stride == 0) if in_backoff else True

            if do_scan and symbols:
                feats = provider.features_for_symbols(symbols)
                provider_calls += 1
                tick_run = run_once(feats)
                runs.append(tick_run)
                panels.append(render_command_room(tick_run, width=width, top_n=top_n))
                last_advice_counts = tick_run["scan"].get("advice_counts", last_advice_counts)
                top_last = tick_run["scan"].get("top", top_last)

        notify = aggregate_alerts(runs) if runs else {"events": [], "counts": {"high":0,"medium":0,"low":0,"info":0}}
        lists_out[name] = {
            "provider_calls": provider_calls,
            "scanned_count": len(panels),
            "panels": panels,
            "advice_counts_last": last_advice_counts or {"attack":0,"defend":0,"standby":0},
            "top_last": top_last,
            "notify": notify,
        }

    return {"lists": lists_out, "ticks": int(ticks)}

def render_battlefield_panel(run_out: Dict[str, Any], width: int, top_n: int) -> str:
    """Mini wrapper around Command Room for per-tick panel output."""
    return render_command_room(run_out, width=width, top_n=top_n)
