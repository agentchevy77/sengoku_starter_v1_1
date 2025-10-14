"""Enhanced operations loop with first-class session logging integration."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from optipanel.ops.session_logger import (
    SessionLogger,
    ensure_safe_logger,
    get_session_logger,
)
from optipanel.runtime.loop import run_once
from optipanel.runtime.scheduler import Job, Scheduler
from optipanel.ui.command_room import render_command_room


def run_watchlist_once_with_logging(
    provider,
    symbols: list[str],
    logger: SessionLogger,
    *,
    width: int,
    top_n: int,
) -> dict[str, Any]:
    """Return analysis artefacts for one watchlist while emitting telemetry."""

    logger = ensure_safe_logger(logger, where="ops_loop_enhanced.run_watchlist_once")

    with logger.operation_context("fetch_features", symbols=symbols):
        raw_features = provider.features_for_symbols(symbols)

    features: dict[str, dict[str, Any]] = {}

    # Process features with error handling
    for sym in symbols:
        try:
            src = dict(raw_features.get(sym, {}))
            last = float(src.get("last", 0.0) or 0.0)

            if last <= 0:
                logger.emit_metric("invalid_price", 1, unit="count")
                last = 100.0

            base: dict[str, Any] = {
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

        except Exception as e:
            logger.emit_error(
                "feature_processing",
                f"Failed to process features for {sym}",
                details={"symbol": sym},
                exception=e,
            )
            # Use fallback features
            features[sym] = {"last": 100.0}

    # Run analysis with logging
    with logger.operation_context("run_analysis", symbol_count=len(features)):
        run = run_once(features)

    # Log alerts if any
    alerts = run.get("alerts", [])
    if alerts:
        logger.emit(
            "alerts_generated",
            {
                "count": len(alerts),
                "symbols": [a.get("symbol") for a in alerts if isinstance(a, dict)],
            },
        )

    # Generate panel
    with logger.operation_context("render_panel"):
        panel = render_command_room(run, width=width, top_n=top_n)

    return {"panel": panel, "run": run}


def make_scheduler_from_profile(profile: Mapping[str, Any]) -> Scheduler:
    """Build a scheduler tuned to the supplied profile budgets."""
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


def ops_loop_enhanced(
    provider,
    profile: Mapping[str, Any],
    *,
    ticks: int,
    sleep: float,
    width: int,
    top_n: int,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Drive the production ops loop with structured telemetry for every step."""

    # Initialize session logger
    with get_session_logger(command="ops_loop", session_id=session_id) as logger:
        # Log configuration
        logger.emit(
            "config",
            {
                "ticks": ticks,
                "sleep": sleep,
                "width": width,
                "top_n": top_n,
                "profile": dict(profile),
            },
        )

        scheduler = make_scheduler_from_profile(profile)
        watchlists = profile.get("watchlists", {}) if isinstance(profile, Mapping) else {}

        # Log watchlist info
        logger.emit(
            "watchlists",
            {
                "count": len(watchlists),
                "names": list(watchlists.keys()),
                "total_symbols": sum(len(v) for v in watchlists.values() if isinstance(v, list)),
            },
        )

        used_seq = []
        prime_budget = profile.get("budgets", {}).get("prime", {}) if isinstance(profile, Mapping) else {}
        seq = prime_budget.get("used_lines") if isinstance(prime_budget, Mapping) else None

        if isinstance(seq, list) and seq:
            used_seq = [int(x) for x in seq]
        if not used_seq:
            used_seq = [1]

        runs: list[dict[str, Any]] = []
        total_alerts = 0

        # Process each tick
        for i in range(int(ticks)):
            tick_start = time.time()

            with logger.operation_context("tick", tick_number=i):
                used = int(used_seq[i % len(used_seq)])
                step = scheduler.step(used)

                # Log scheduler state
                logger.emit(
                    "scheduler_step",
                    {
                        "tick": step["tick"],
                        "backoff": step["backoff"],
                        "due": step["due"],
                        "used_lines": used,
                    },
                )

                # Process due watchlists
                for name in step["due"]:
                    symbols = list(watchlists.get(name, []))
                    if not symbols:
                        logger.emit(
                            "watchlist_skipped",
                            {
                                "name": name,
                                "reason": "empty",
                            },
                        )
                        continue

                    try:
                        with logger.operation_context("process_watchlist", name=name):
                            result = run_watchlist_once_with_logging(
                                provider,
                                symbols,
                                logger,
                                width=width,
                                top_n=top_n,
                            )

                            # Track alerts
                            alerts = result.get("run", {}).get("alerts", [])
                            total_alerts += len(alerts)

                            runs.append(
                                {
                                    "list": name,
                                    "tick": step["tick"],
                                    "panel": result["panel"],
                                    "alert_count": len(alerts),
                                }
                            )

                            # Output panel
                            print(f"\n=== {name.upper()} @ tick {step['tick']} (backoff={step['backoff']}) ===")
                            print(result["panel"])

                    except Exception as e:
                        logger.emit_error(
                            "watchlist_processing",
                            f"Failed to process watchlist {name}",
                            details={"watchlist": name, "tick": i},
                            exception=e,
                        )

                # Log tick metrics
                tick_duration_ms = (time.time() - tick_start) * 1000
                logger.emit_metric("tick_duration", tick_duration_ms, unit="ms")

                if sleep and i < (ticks - 1):
                    time.sleep(float(sleep))

        # Log final summary
        logger.emit(
            "summary",
            {
                "total_ticks": ticks,
                "total_runs": len(runs),
                "total_alerts": total_alerts,
                "final_backoff": scheduler.state.backoff,
                "avg_alerts_per_run": total_alerts / len(runs) if runs else 0,
            },
        )

        return {
            "ticks": ticks,
            "backoff": scheduler.state.backoff,
            "runs": runs,
            "session_id": logger.session_id,
            "total_alerts": total_alerts,
        }
