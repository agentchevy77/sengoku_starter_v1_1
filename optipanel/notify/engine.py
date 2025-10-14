from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from optipanel.models.alert import AlertPayload
from optipanel.notify.utils import (
    invalid_symbol_token,
    normalize_severity,
    normalize_symbol,
    severity_rank,
)
from optipanel.utils.safe_error_handler import SafeErrorHandler
from optipanel.utils.safe_ops import safe_int

logger = logging.getLogger(__name__)

_error_handler = SafeErrorHandler(logger=logger, context="notify.engine")

# ---------------------------------------------------------------------------
# Backwards compatibility exports
# ---------------------------------------------------------------------------
#
# Several legacy tests (and likely external callers) still import the helper
# utilities with their historic underscored names from this module.  The
# helpers were recently factored into optipanel.notify.utils, which broke those
# imports and caused the full regression suite to fail during collection.  To
# retain the refactor while restoring compatibility, re-export the helpers by
# their original names.
_invalid_symbol_token = invalid_symbol_token
_normalize_symbol = normalize_symbol
_normalize_severity = normalize_severity
_rank = severity_rank


def _safe_magnitude(value: Any, threshold: Any, context: str = "") -> float | None:
    try:
        val_float = float(value) if value is not None else 0.0
        thresh_float = float(threshold) if threshold is not None else 0.0
        return abs(val_float - thresh_float)
    except (ValueError, TypeError, OverflowError) as exc:
        _error_handler.safe_exception(
            "notify.magnitude_calc_failed%s: value=%s, threshold=%s, error=%s",
            f" ({context})" if context else "",
            value,
            threshold,
            type(exc).__name__,
        )
        return None


class AlertIndex:
    __slots__ = ("_events", "_by_symbol", "_by_kind", "_by_severity", "_indexed")

    def __init__(self, events: list[dict[str, Any]] | None = None):
        self._events: list[dict[str, Any]] = events if events is not None else []
        self._by_symbol: dict[str, list[dict[str, Any]]] = {}
        self._by_kind: dict[str, list[dict[str, Any]]] = {}
        self._by_severity: dict[str, list[dict[str, Any]]] = {}
        self._indexed: bool = False

    def _build_indexes(self) -> None:
        if self._indexed:
            return

        by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_severity: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for event in self._events:
            original_symbol = event.get("symbol")
            symbol, symbol_issue = normalize_symbol(original_symbol)
            if symbol_issue:
                if "raw_symbol" not in event:
                    event["raw_symbol"] = "" if original_symbol is None else str(original_symbol)
                logger.warning(
                    "notify.alert_index.symbol_normalized: original=%r sanitized=%s reason=%s",
                    original_symbol,
                    symbol,
                    symbol_issue,
                )
            event["symbol"] = symbol

            kind = str(event.get("kind", ""))

            raw_severity = event.get("severity")
            if isinstance(raw_severity, str):
                trimmed = raw_severity.strip()
                severity = "" if trimmed == "" else normalize_severity(raw_severity)
            else:
                severity = normalize_severity(raw_severity)

            by_symbol[symbol].append(event)
            by_kind[kind].append(event)
            by_severity[severity].append(event)

        self._by_symbol = dict(by_symbol)
        self._by_kind = dict(by_kind)
        self._by_severity = dict(by_severity)
        self._indexed = True

    def by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        self._build_indexes()
        return self._by_symbol.get(symbol, [])

    def by_kind(self, kind: str) -> list[dict[str, Any]]:
        self._build_indexes()
        return self._by_kind.get(kind, [])

    def by_severity(self, severity: str) -> list[dict[str, Any]]:
        self._build_indexes()

        if severity is None:
            lookup = normalize_severity(None)
        else:
            query = str(severity).strip()
            if query == "":
                lookup = ""
            else:
                normalized = normalize_severity(query)
                if (
                    normalized == "info"
                    and severity_rank(query) == 1
                    and query.lower() not in ("info", "low", "medium", "high")
                ):
                    return []
                lookup = normalized

        return self._by_severity.get(lookup, [])

    def top_n(self, n: int, severity: str | None = None) -> list[dict[str, Any]]:
        candidates = self.by_severity(severity) if severity else self._events
        return candidates[:n] if n > 0 else candidates

    def all_events(self) -> list[dict[str, Any]]:
        return self._events

    def symbols(self) -> list[str]:
        self._build_indexes()
        return list(self._by_symbol.keys())

    def kinds(self) -> list[str]:
        self._build_indexes()
        return list(self._by_kind.keys())

    def severities(self) -> list[str]:
        self._build_indexes()
        return list(self._by_severity.keys())

    def stats(self) -> dict[str, Any]:
        self._build_indexes()
        breakdown: dict[str, int] = {}
        for severity, events in self._by_severity.items():
            if severity == "":
                breakdown["info"] = breakdown.get("info", 0) + len(events)
            else:
                breakdown[severity] = len(events)
        return {
            "total_events": len(self._events),
            "unique_symbols": len(self._by_symbol),
            "unique_kinds": len(self._by_kind),
            "severity_breakdown": breakdown,
        }


def update_bus(bus: dict[tuple[str, str], dict[str, Any]], alerts: Any, tick_index: int) -> None:
    if alerts is None:
        return

    if isinstance(alerts, Mapping):
        candidates = [alerts]
    elif isinstance(alerts, (str, int, float, bool)):
        logger.error(
            "notify.update_bus: expected iterable or mapping, got primitive type '%s' (expected iterable of alert mappings)",
            type(alerts).__name__,
        )
        return
    else:
        try:
            candidates = list(alerts)
        except TypeError:
            logger.error(
                "notify.update_bus: alerts payload of type %s is not iterable or mapping",
                type(alerts).__name__,
            )
            return

    if not candidates:
        return

    validated: list[AlertPayload] = []
    for idx, entry in enumerate(candidates):
        if entry is None:
            logger.warning("notify.update_bus: skipping None alert payload at index %d", idx)
            continue

        if not isinstance(entry, Mapping):
            logger.error(
                "notify.update_bus: skipping alerts[%d] of unsupported type %s",
                idx,
                type(entry).__name__,
            )
            logger.warning(
                "notify.update_bus: skipping invalid/failed validation alert payload at index %d",
                idx,
            )
            continue

        payload = AlertPayload.parse_and_validate(entry)
        if payload:
            validated.append(payload)
        else:
            logger.warning(
                "notify.update_bus: skipping invalid/failed validation alert payload at index %d",
                idx,
            )

    for payload in validated:
        raw_payload: Mapping[str, Any] = getattr(payload, "_raw_payload", {})
        sanitized_data = payload.model_dump()
        for optional_field in ("sustainment", "supply", "gate", "readiness"):
            if sanitized_data.get(optional_field) is None and optional_field not in raw_payload:
                sanitized_data.pop(optional_field, None)
        sym = payload.symbol
        kind = payload.kind
        key = (sym, kind)
        event = bus.get(key)
        tick_context = f"{sym}/{kind}"

        if event is None:
            prior_tick = 0
        else:
            prior_tick = safe_int(
                event.get("last_seen_tick"),
                default=0,
                warn=False,
                context=f"notify.last_seen_tick[{tick_context}]",
            )
        tick_value = safe_int(
            tick_index,
            default=prior_tick,
            context=f"notify.tick_index[{tick_context}]",
        )

        if event is None:
            event_obj = AlertEvent(sanitized_data, raw_payload)
            event_obj.update(
                {
                    "count": 1,
                    "first_seen_tick": tick_value,
                    "last_seen_tick": tick_value,
                }
            )
            bus[key] = event_obj
            continue

        if not isinstance(event, AlertEvent):
            replacement = AlertEvent(event, event)
            bus[key] = replacement
            event = replacement

        event["count"] += 1
        event["last_seen_tick"] = tick_value

        if severity_rank(payload.severity) > severity_rank(event.get("severity")):
            event["severity"] = payload.severity

        raw_symbol_val = raw_payload.get("raw_symbol", sanitized_data.get("raw_symbol"))
        if raw_symbol_val and ("raw_symbol" not in event or event["raw_symbol"] is None):
            event["raw_symbol"] = raw_symbol_val

        for field in ("sustainment", "supply", "gate", "readiness"):
            value = raw_payload.get(field, sanitized_data.get(field))
            if value and (field not in event or event[field] is None):
                event[field] = deepcopy(value)

        new_val_raw = raw_payload.get("value", sanitized_data.get("value"))
        new_thresh_raw = raw_payload.get("threshold", sanitized_data.get("threshold"))
        old_mag = _safe_magnitude(event.get_raw("value"), event.get_raw("threshold"), context=f"old:{sym}/{kind}")
        new_mag = _safe_magnitude(new_val_raw, new_thresh_raw, context=f"new:{sym}/{kind}")

        update_values = False
        if new_mag is not None:
            if old_mag is None or event.get("value") is None or event.get("threshold") is None:
                update_values = True
                if old_mag is None:
                    logger.warning(
                        "notify.update_bus.old_magnitude_invalid for %s/%s, using new values",
                        sym,
                        kind,
                    )
            elif new_mag > old_mag:
                update_values = True

        if update_values:
            event.set_numeric("value", sanitized_data.get("value"), new_val_raw)
            event.set_numeric("threshold", sanitized_data.get("threshold"), new_thresh_raw)

        message_val = raw_payload.get("message", sanitized_data.get("message"))
        if message_val:
            event["message"] = message_val


def aggregate_alerts(runs: list[dict[str, Any]], *, use_index: bool = False) -> dict[str, Any]:
    bus: dict[tuple[str, str], dict[str, Any]] = {}
    for idx, run in enumerate(runs or []):
        update_bus(bus, run.get("alerts"), tick_index=idx)

    events = list(bus.values())

    def magnitude(alert: dict[str, Any]) -> float:
        value = alert.get("value")
        threshold = alert.get("threshold")
        if hasattr(alert, "get_raw"):
            value = alert.get_raw("value")
            threshold = alert.get_raw("threshold")

        result = _safe_magnitude(
            value,
            threshold,
            context=f"sort:{alert.get('symbol')}/{alert.get('kind')}",
        )
        return result if result is not None else 0.0

    def _safe_last_seen(alert: dict[str, Any]) -> int:
        context = f"aggregate.last_seen_tick:{alert.get('symbol', '')}/{alert.get('kind', '')}"
        return safe_int(alert.get("last_seen_tick"), default=0, warn=False, context=context)

    events.sort(
        key=lambda alert: (
            severity_rank(alert.get("severity")),
            _safe_last_seen(alert),
            magnitude(alert),
        ),
        reverse=True,
    )

    counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for alert in events:
        severity = alert.get("severity", "info")
        if severity_rank(severity) == 1 and severity not in counts:
            severity = normalize_severity(severity)
        counts[severity] = counts.get(severity, 0) + 1

    if use_index:
        return {"events": AlertIndex(events), "counts": counts}
    return {"events": events, "counts": counts}


class AlertEvent(dict):
    """Dictionary wrapper that preserves both raw and sanitised numeric fields."""

    __slots__ = ("_sanitized_numeric",)

    def __init__(self, sanitized: Mapping[str, Any], raw: Mapping[str, Any]):
        super().__init__()
        self._sanitized_numeric: dict[str, Any] = {}

        for key, value in sanitized.items():
            if key in {"value", "threshold"}:
                self._sanitized_numeric[key] = value
            super().__setitem__(key, deepcopy(value))

        for key in ("value", "threshold"):
            if key in raw:
                super().__setitem__(key, deepcopy(raw[key]))

    def get(self, key, default=None):  # type: ignore[override]
        if key in self._sanitized_numeric:
            return self._sanitized_numeric.get(key, default)
        return super().get(key, default)

    def get_raw(self, key: str, default=None):
        return dict.get(self, key, default)

    def set_numeric(self, key: str, sanitized_value: Any, raw_value: Any) -> None:
        if key not in {"value", "threshold"}:
            super().__setitem__(key, deepcopy(raw_value))
            return

        self._sanitized_numeric[key] = sanitized_value
        if raw_value is not None:
            super().__setitem__(key, deepcopy(raw_value))
        else:
            super().__setitem__(key, deepcopy(sanitized_value))
