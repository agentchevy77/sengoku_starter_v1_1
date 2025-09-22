from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PacingAlert:
    severity: str
    message: str
    last_wait_sec: float
    total_wait_sec: float
    interval_sec: float
    max_requests: int


DEFAULT_THRESHOLDS = {
    "last_wait_warn": 1.0,
    "last_wait_crit": 3.0,
    "total_ratio_warn": 0.15,
    "total_ratio_crit": 0.35,
}


_ENV_MAP = {
    "SENGOKU_TWS_PACING_LAST_WAIT_WARN": "last_wait_warn",
    "SENGOKU_TWS_PACING_LAST_WAIT_CRIT": "last_wait_crit",
    "SENGOKU_TWS_PACING_TOTAL_RATIO_WARN": "total_ratio_warn",
    "SENGOKU_TWS_PACING_TOTAL_RATIO_CRIT": "total_ratio_crit",
}

_logger = logging.getLogger(__name__)


def load_thresholds_from_env(env: Mapping[str, str] | None = None) -> dict[str, float]:
    source = env or os.environ
    overrides: dict[str, float] = {}
    for var, key in _ENV_MAP.items():
        raw = source.get(var)
        if raw is None:
            continue
        try:
            overrides[key] = float(raw)
        except ValueError:
            _logger.warning("Ignoring pacing threshold env '%s': cannot parse '%s'", var, raw)
    return overrides


def evaluate_pacing_alerts(
    metrics: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> list[PacingAlert]:
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update({k: float(v) for k, v in thresholds.items()})

    max_requests = int(metrics.get("global_rate_max_requests", 0) or 0)
    interval_sec = float(metrics.get("global_rate_interval_sec", 0.0) or 0.0)
    last_wait = float(metrics.get("global_rate_last_wait_sec", 0.0) or 0.0)
    total_wait = float(metrics.get("global_rate_total_wait_sec", 0.0) or 0.0)

    alerts: list[PacingAlert] = []
    if interval_sec <= 0 or max_requests <= 0:
        return alerts

    ratio = total_wait / interval_sec if interval_sec else 0.0

    if last_wait >= th["last_wait_crit"]:
        alerts.append(
            PacingAlert(
                severity="high",
                message=(
                    f"IBKR global rate limiter is sleeping {last_wait:.2f}s per request "
                    f"(threshold {th['last_wait_crit']:.2f}s)."
                ),
                last_wait_sec=last_wait,
                total_wait_sec=total_wait,
                interval_sec=interval_sec,
                max_requests=max_requests,
            )
        )
    elif last_wait >= th["last_wait_warn"]:
        alerts.append(
            PacingAlert(
                severity="medium",
                message=(
                    f"IBKR global rate limiter wait {last_wait:.2f}s exceeds warning "
                    f"threshold {th['last_wait_warn']:.2f}s."
                ),
                last_wait_sec=last_wait,
                total_wait_sec=total_wait,
                interval_sec=interval_sec,
                max_requests=max_requests,
            )
        )

    if ratio >= th["total_ratio_crit"]:
        alerts.append(
            PacingAlert(
                severity="high",
                message=(
                    f"IBKR global rate limiter consumed {ratio * 100.0:.0f}% of window in waits "
                    f"(threshold {th['total_ratio_crit'] * 100.0:.0f}%)."
                ),
                last_wait_sec=last_wait,
                total_wait_sec=total_wait,
                interval_sec=interval_sec,
                max_requests=max_requests,
            )
        )
    elif ratio >= th["total_ratio_warn"]:
        alerts.append(
            PacingAlert(
                severity="medium",
                message=(
                    f"IBKR global pacing waits at {ratio * 100.0:.0f}% of window "
                    f"(warning {th['total_ratio_warn'] * 100.0:.0f}%)."
                ),
                last_wait_sec=last_wait,
                total_wait_sec=total_wait,
                interval_sec=interval_sec,
                max_requests=max_requests,
            )
        )

    deduped: dict[str, PacingAlert] = {}
    for alert in alerts:
        deduped.setdefault(alert.message, alert)
    return list(deduped.values())
