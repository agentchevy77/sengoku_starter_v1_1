from __future__ import annotations

import os
from typing import Any

from optipanel.recon.enrich import enrich_alerts_with_supply_sustain

DEFAULT_THRESH: dict[str, int] = {
    "score_attack": 65,
    "score_defend": 35,
    "breakout_up": 80,
    "breakdown_down": 80,
    "bounce_up": 70,
    "rejection_down": 70,
    "trend_long": 70,
    "trend_short": 70,
    "exhaustion": 75,
}


def _sev(value: int, thresh: int) -> str:
    if value >= thresh + 15:
        return "high"
    if value >= thresh + 5:
        return "medium"
    return "low"


def gen_alerts(snapshot: dict[str, Any], thresholds: dict[str, int] | None = None) -> list[dict[str, Any]]:
    th = thresholds or DEFAULT_THRESH
    symbol = snapshot.get("symbol", "?")
    score = int(snapshot.get("score", 0))
    setups = snapshot.get("setups", {}) or {}

    out: list[dict[str, Any]] = []

    # Score-based alerts
    if score >= th["score_attack"]:
        out.append(
            {
                "symbol": symbol,
                "kind": "score_attack",
                "value": score,
                "threshold": th["score_attack"],
                "severity": _sev(score, th["score_attack"]),
                "message": f"{symbol} score_attack {score} >= {th['score_attack']}",
            }
        )
    if score <= th["score_defend"]:
        sev = "high" if score <= th["score_defend"] - 15 else ("medium" if score <= th["score_defend"] - 5 else "low")
        out.append(
            {
                "symbol": symbol,
                "kind": "score_defend",
                "value": score,
                "threshold": th["score_defend"],
                "severity": sev,
                "message": f"{symbol} score_defend {score} <= {th['score_defend']}",
            }
        )

    # Setup-based alerts (trigger on >= threshold)
    keys = ["breakout_up", "breakdown_down", "bounce_up", "rejection_down", "trend_long", "trend_short", "exhaustion"]
    for k in keys:
        v = int(setups.get(k, 0))
        t = th.get(k, 999)
        if v >= t:
            out.append(
                {
                    "symbol": symbol,
                    "kind": k,
                    "value": v,
                    "threshold": t,
                    "severity": _sev(v, t),
                    "message": f"{symbol} {k} {v} >= {t}",
                }
            )

    return out


def analyze_batch(snapshots: list[dict[str, Any]], thresholds: dict[str, int] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in snapshots:
        out.extend(gen_alerts(s, thresholds))
    return out


def analyze_batch_with_supply(
    snapshots: list[dict[str, Any]],
    thresholds: dict[str, int] | None = None,
    include_supply: bool | None = None,
) -> list[dict[str, Any]]:
    base = analyze_batch(snapshots, thresholds)
    if include_supply is None:
        include_supply = os.getenv("SENGOKU_ALERTS_INCLUDE_SUPPLY", "") == "1"
    return enrich_alerts_with_supply_sustain(
        snapshots,
        base,
        include_supply=include_supply,
        include_sustain=True,
    )
