from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from optipanel.runtime.loop import run_once
from optipanel.runtime.scheduler import Job, Scheduler
from optipanel.ui.command_room import render_command_room


def run_watchlist_once(provider, symbols: list[str], *, width: int, top_n: int) -> dict[str, Any]:
    raw_features = provider.features_for_symbols(symbols)
    features: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        src = dict(raw_features.get(sym, {}))
        last = float(src.get("last", 0.0) or 0.0)
        if last <= 0:
            last = 100.0
        base = {
            "last": last,
            "dma20": float(src.get("dma20", last)),
            "support": float(src.get("support", last * 0.96)),
            "resistance": float(src.get("resistance", last * 1.04)),
            "rvol": float(src.get("rvol", 1.0)),
            "rs_strength": float(src.get("rs_strength", 0.0)),
            "vwap_diff": float(src.get("vwap_diff", 0.0)),
        }
        bundles_obj = src.get("bundles")
        bundles = dict(bundles_obj) if isinstance(bundles_obj, dict) else {}
        one_day = dict(bundles.get("1d", {}))
        if float(one_day.get("last", 0.0) or 0.0) <= 0:
            one_day = dict(base)
        else:
            one_day.setdefault("dma20", base["dma20"])
            one_day.setdefault("support", base["support"])
            one_day.setdefault("resistance", base["resistance"])
            one_day.setdefault("rvol", base["rvol"])
            one_day.setdefault("rs_strength", base["rs_strength"])
            one_day.setdefault("vwap_diff", base["vwap_diff"])
        bundles["1d"] = one_day
        base["bundles"] = bundles
        features[sym] = base

    run = run_once(features)
    panel = render_command_room(run, width=width, top_n=top_n)
    return {"panel": panel, "run": run}


def make_scheduler_from_profile(profile: Mapping[str, Any]) -> Scheduler:
    budgets = profile.get("budgets", {}) if isinstance(profile, Mapping) else {}
    prime = budgets.get("prime", {}) if isinstance(budgets, Mapping) else {}
    secondary = budgets.get("secondary", {}) if isinstance(budgets, Mapping) else {}

    soft_cap = int(prime.get("soft_cap", 20))
    cooldown = int(prime.get("cooldown", 2))

    stride_prime = int(prime.get("scan_stride", prime.get("scan_stride_backoff", 1)))
    stride_secondary = int(secondary.get("scan_stride", 6))

    jobs = {
        "prime": Job("prime", stride_prime),
        "secondary": Job("secondary", stride_secondary),
    }
    return Scheduler(jobs, soft_cap=soft_cap, cooldown=cooldown)


def ops_loop(
    provider,
    profile: Mapping[str, Any],
    *,
    ticks: int,
    sleep: float,
    width: int,
    top_n: int,
) -> dict[str, Any]:
    scheduler = make_scheduler_from_profile(profile)
    watchlists = profile.get("watchlists", {}) if isinstance(profile, Mapping) else {}

    used_seq = []
    prime_budget = profile.get("budgets", {}).get("prime", {}) if isinstance(profile, Mapping) else {}
    seq = prime_budget.get("used_lines") if isinstance(prime_budget, Mapping) else None
    if isinstance(seq, list) and seq:
        used_seq = [int(x) for x in seq]
    if not used_seq:
        used_seq = [1]

    runs: list[dict[str, Any]] = []
    for i in range(int(ticks)):
        used = int(used_seq[i % len(used_seq)])
        step = scheduler.step(used)

        for name in step["due"]:
            symbols = list(watchlists.get(name, []))
            if not symbols:
                continue
            result = run_watchlist_once(provider, symbols, width=width, top_n=top_n)
            runs.append({"list": name, "tick": step["tick"], "panel": result["panel"]})
            print(f"\n=== {name.upper()} @ tick {step['tick']} (backoff={step['backoff']}) ===")
            print(result["panel"])

        if sleep and i < (ticks - 1):
            time.sleep(float(sleep))

    return {"ticks": ticks, "backoff": scheduler.state.backoff, "runs": runs}
