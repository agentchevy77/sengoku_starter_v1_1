from __future__ import annotations

import logging
from typing import Any

from optipanel.notify.engine import aggregate_alerts
from optipanel.runtime.driver import LocalBudget, _expand_usage
from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room

logger = logging.getLogger(__name__)


def run_profiles_with_provider(profiles_cfg: dict[str, Any], provider: Any, ticks: int = 3) -> dict[str, Any]:
    """
    Drive each watchlist through a budget/backoff loop.
    On scan ticks, fetch features from provider and run the pure decision loop,
    collect Command Room panels, and aggregate alerts for a notifications strip.
    """
    ui = profiles_cfg.get("ui", {})
    width = int(ui.get("width", 24))
    top_n = int(ui.get("top_n", 1))

    watchlists = profiles_cfg.get("watchlists", {})
    budgets = profiles_cfg.get("budgets", {})

    ticks_int = max(1, int(ticks))

    contexts: dict[str, dict[str, Any]] = {}
    for name, symbols in (watchlists or {}).items():
        symbols = list(symbols or [])
        budget_cfg = dict(budgets.get(name, {}))
        soft_cap = int(budget_cfg.get("soft_cap", 10))
        cooldown = int(budget_cfg.get("cooldown", 2))
        stride = int(budget_cfg.get("scan_stride_backoff", 2))
        usage_seq = _expand_usage(budget_cfg.get("used_lines", 0), ticks_int)

        contexts[name] = {
            "symbols": symbols,
            "budget": LocalBudget(soft_cap=soft_cap, cooldown=cooldown),
            "stride": max(1, stride),
            "usage_seq": usage_seq,
            "panels": [],
            "provider_calls": 0,
            "last_advice_counts": None,
            "top_last": [],
            "runs": [],
        }

    for tick_i in range(ticks_int):
        per_tick_cache: dict[str, dict[str, Any]] = {}
        to_scan: list[tuple[str, dict[str, Any]]] = []
        union_symbols: list[str] = []

        seen_symbols: set[str] = set()

        for name, ctx in contexts.items():
            symbols = ctx["symbols"]
            if not symbols:
                continue
            used = int(ctx["usage_seq"][tick_i])
            in_backoff = ctx["budget"].step(used)
            do_scan = (tick_i % ctx["stride"] == 0) if in_backoff else True
            logger.debug(
                "profiles_live: tick=%d list=%s used=%d backoff=%s do_scan=%s",
                tick_i,
                name,
                used,
                in_backoff,
                do_scan,
            )
            if do_scan:
                to_scan.append((name, ctx))
                for sym in symbols:
                    if sym in seen_symbols:
                        continue
                    seen_symbols.add(sym)
                    if sym not in per_tick_cache:
                        union_symbols.append(sym)

        if to_scan and union_symbols:
            fetched = provider.features_for_symbols(union_symbols) or {}
            logger.info(
                "profiles_live: tick=%d fetched_symbols=%s",
                tick_i,
                ",".join(union_symbols),
            )
            for sym in union_symbols:
                per_tick_cache[sym] = dict(fetched.get(sym, {}))

        for name, ctx in to_scan:
            symbols = ctx["symbols"]
            feats = {sym: per_tick_cache.get(sym, {}) for sym in symbols}
            logger.debug(
                "profiles_live: tick=%d list=%s symbols=%s",
                tick_i,
                name,
                ",".join(symbols),
            )
            tick_run = run_once(feats)
            ctx["runs"].append(tick_run)
            ctx["panels"].append(render_command_room(tick_run, width=width, top_n=top_n))
            ctx["provider_calls"] += 1
            ctx["last_advice_counts"] = tick_run["scan"].get("advice_counts", ctx["last_advice_counts"])
            ctx["top_last"] = tick_run["scan"].get("top", ctx["top_last"])

    lists_out: dict[str, Any] = {}
    for name, ctx in contexts.items():
        runs = ctx["runs"]
        notify = (
            aggregate_alerts(runs) if runs else {"events": [], "counts": {"high": 0, "medium": 0, "low": 0, "info": 0}}
        )
        lists_out[name] = {
            "provider_calls": ctx["provider_calls"],
            "scanned_count": len(ctx["panels"]),
            "panels": ctx["panels"],
            "advice_counts_last": ctx["last_advice_counts"] or {"attack": 0, "defend": 0, "standby": 0},
            "top_last": ctx["top_last"],
            "notify": notify,
        }

    return {"lists": lists_out, "ticks": ticks_int}


def render_battlefield_panel(run_out: dict[str, Any], width: int, top_n: int) -> str:
    """Mini wrapper around Command Room for per-tick panel output."""
    return render_command_room(run_out, width=width, top_n=top_n)
