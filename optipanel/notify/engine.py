from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from optipanel.utils.safe_error_handler import SafeErrorHandler
from optipanel.utils.safe_ops import safe_int

logger = logging.getLogger(__name__)

# Create safe error handler for this module
_error_handler = SafeErrorHandler(logger=logger, context="notify.engine")

_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 1}

_SYMBOL_PLACEHOLDER = "__INVALID_SYMBOL__"
_SYMBOL_MAX_LENGTH = 48
_ALLOWED_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._:/@+\-^]+$")
_ALLOWED_PREFIX_PATTERN = re.compile(r"^[A-Z0-9._:/@+\-^]+")


def _invalid_symbol_token(tag: str, source: str) -> str:
    """Build a deterministic, safe token for invalid symbols."""

    digest_source = source.encode("utf-8", "ignore") or tag.upper().encode("ascii")
    digest = hashlib.sha1(digest_source).hexdigest().upper()
    cleaned_tag = tag.upper()
    return f"{_SYMBOL_PLACEHOLDER}-{cleaned_tag}-{digest[:6]}"


def _normalize_symbol(raw: Any) -> tuple[str, str | None]:
    """Sanitize symbol values to prevent injection and ensure consistent indexing.

    Returns a tuple of (sanitized_symbol, issue_reason). issue_reason is ``None``
    when the symbol was already valid. When the symbol cannot be trusted it falls
    back to ``_SYMBOL_PLACEHOLDER`` and the reason describes the failure.
    """

    if raw is None:
        return _invalid_symbol_token("missing", ""), "missing"

    raw_str = str(raw)
    candidate = raw_str.strip()
    trimmed = candidate != raw_str

    if not candidate:
        return _invalid_symbol_token("empty", ""), "empty"

    canonical = candidate.upper()
    if len(canonical) > _SYMBOL_MAX_LENGTH:
        return _invalid_symbol_token("toolong", canonical), "too_long"

    if _ALLOWED_SYMBOL_PATTERN.fullmatch(canonical):
        return canonical, "whitespace" if trimmed else None

    # If invalid characters are present, attempt to recover a trustworthy prefix
    # that contains only allowed characters and is not followed by alphanumerics.
    # This preserves legitimate symbols that are tailed by whitespace or control
    # characters (e.g. "AAPL\n").
    prefix_match = _ALLOWED_PREFIX_PATTERN.match(canonical)
    if prefix_match:
        prefix = prefix_match.group(0)
        remainder = canonical[len(prefix) :]
        if prefix and not any(ch.isalnum() for ch in remainder):
            return prefix, "invalid_suffix"

    return _invalid_symbol_token("badchar", canonical), "invalid_chars"


def _normalize_severity(severity: Any) -> str:
    """
    Normalize severity value to valid lowercase string.

    FIX for Bug #74: Properly handles None and edge cases.

    Previously, str(None) would produce "none" instead of using default "info".
    This function ensures None, empty strings, and invalid values default to "info".

    Args:
        severity: Raw severity value (can be None, str, int, etc.)

    Returns:
        Normalized severity string: "high", "medium", "low", or "info" (default)

    Examples:
        >>> _normalize_severity(None)
        'info'
        >>> _normalize_severity("")
        'info'
        >>> _normalize_severity("HIGH")
        'high'
        >>> _normalize_severity("medium")
        'medium'
    """
    if severity is None or severity == "":
        return "info"

    try:
        severity_str = str(severity).strip().lower()
        # Validate against known severity levels
        if severity_str in _SEV_RANK:
            return severity_str
        else:
            # Unknown severity - default to info
            logger.debug(
                "notify._normalize_severity: unknown severity=%r, defaulting to 'info'",
                severity,
            )
            return "info"
    except Exception as e:
        # Conversion failed - log and default to info
        _error_handler.safe_exception(
            "notify._normalize_severity: conversion failed for severity=%r, error=%s",
            severity,
            type(e).__name__,
        )
        return "info"


def _rank(s: Any) -> int:
    return _SEV_RANK.get(str(s).lower(), 1)


class AlertIndex:
    """
    Bug #80 Fix: Efficient secondary indexes for alert queries.

    Provides O(1) filtered queries on alert events without requiring full scans.
    Maintains indexes by symbol, kind, and severity for fast lookups.

    Usage:
        index = AlertIndex(events)
        high_alerts = index.by_severity("high")  # O(k) instead of O(n)
        aapl_alerts = index.by_symbol("AAPL")     # O(m) instead of O(n)
    """

    __slots__ = ("_events", "_by_symbol", "_by_kind", "_by_severity", "_indexed")

    def __init__(self, events: list[dict[str, Any]] | None = None):
        """
        Initialize AlertIndex with optional events list.

        Args:
            events: List of alert event dictionaries. Can be None for lazy init.
        """
        self._events: list[dict[str, Any]] = events if events is not None else []
        self._by_symbol: dict[str, list[dict[str, Any]]] = {}
        self._by_kind: dict[str, list[dict[str, Any]]] = {}
        self._by_severity: dict[str, list[dict[str, Any]]] = {}
        self._indexed: bool = False

    def _build_indexes(self) -> None:
        """Build secondary indexes from events list. Called lazily on first query."""
        if self._indexed:
            return

        # Use defaultdict for cleaner code
        by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_severity: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for event in self._events:
            original_symbol = event.get("symbol")
            symbol, symbol_issue = _normalize_symbol(original_symbol)
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
                # Preserve explicit empty severities (Bug #80 regression fix)
                severity = "" if trimmed == "" else _normalize_severity(raw_severity)
            else:
                # Non-string severities still normalize through the shared helper
                severity = _normalize_severity(raw_severity)

            by_symbol[symbol].append(event)
            by_kind[kind].append(event)
            by_severity[severity].append(event)

        self._by_symbol = dict(by_symbol)
        self._by_kind = dict(by_kind)
        self._by_severity = dict(by_severity)
        self._indexed = True

    def by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get all alerts for a specific symbol. O(k) where k = number of alerts for symbol.

        Args:
            symbol: The symbol to filter by (e.g., "AAPL")

        Returns:
            List of alert events for the symbol. Empty list if none found.
        """
        self._build_indexes()
        return self._by_symbol.get(symbol, [])

    def by_kind(self, kind: str) -> list[dict[str, Any]]:
        """
        Get all alerts of a specific kind. O(m) where m = number of alerts of that kind.

        Args:
            kind: The alert kind to filter by (e.g., "trend_long")

        Returns:
            List of alert events of that kind. Empty list if none found.
        """
        self._build_indexes()
        return self._by_kind.get(kind, [])

    def by_severity(self, severity: str) -> list[dict[str, Any]]:
        """
        Get all alerts of a specific severity. O(s) where s = number of alerts with that severity.

        Args:
            severity: The severity level (e.g., "high", "medium", "low", "info")

        Returns:
            List of alert events with that severity. Empty list if none found.
        """
        self._build_indexes()

        if severity is None:
            lookup = _normalize_severity(None)
        else:
            query = str(severity).strip()
            if query == "":
                lookup = ""
            else:
                normalized = _normalize_severity(query)
                if normalized == "info" and query.lower() not in _SEV_RANK:
                    # Preserve legacy behaviour: unknown values (e.g. "none") have no bucket
                    return []
                lookup = normalized

        return self._by_severity.get(lookup, [])

    def top_n(self, n: int, severity: str | None = None) -> list[dict[str, Any]]:
        """
        Get top N alerts, optionally filtered by severity.

        Args:
            n: Number of alerts to return
            severity: Optional severity filter (e.g., "high")

        Returns:
            Top N alerts (already sorted by aggregate_alerts)
        """
        candidates = self.by_severity(severity) if severity else self._events

        return candidates[:n] if n > 0 else candidates

    def all_events(self) -> list[dict[str, Any]]:
        """Return all events (no filtering)."""
        return self._events

    def symbols(self) -> list[str]:
        """Get list of all unique symbols with alerts."""
        self._build_indexes()
        return list(self._by_symbol.keys())

    def kinds(self) -> list[str]:
        """Get list of all unique alert kinds."""
        self._build_indexes()
        return list(self._by_kind.keys())

    def severities(self) -> list[str]:
        """Get list of all unique severity levels present."""
        self._build_indexes()
        return list(self._by_severity.keys())

    def stats(self) -> dict[str, Any]:
        """
        Get index statistics for monitoring/debugging.

        Returns:
            Dict with index stats (total events, unique symbols, kinds, severities)
        """
        self._build_indexes()
        breakdown: dict[str, int] = {}
        for sev, events in self._by_severity.items():
            if sev == "":
                # Empty severities (explicit blanks) are reported under info for metrics compatibility
                breakdown["info"] = breakdown.get("info", 0) + len(events)
            else:
                breakdown[sev] = len(events)
        return {
            "total_events": len(self._events),
            "unique_symbols": len(self._by_symbol),
            "unique_kinds": len(self._by_kind),
            "severity_breakdown": breakdown,
        }


def _safe_magnitude(value: Any, threshold: Any, context: str = "") -> float | None:
    """
    Safely calculate magnitude as abs(value - threshold).

    Returns:
        Magnitude as float if calculation succeeds, None otherwise.

    Bug #82 Fix: Separated magnitude calculation to enable granular error handling.
    """
    try:
        val_float = float(value) if value is not None else 0.0
        thresh_float = float(threshold) if threshold is not None else 0.0
        return abs(val_float - thresh_float)
    except (ValueError, TypeError, OverflowError) as e:
        # Log specific error with context to aid debugging
        _error_handler.safe_exception(
            "notify.magnitude_calc_failed%s: value=%s, threshold=%s, error=%s",
            f" ({context})" if context else "",
            value,
            threshold,
            type(e).__name__,
        )
        return None


def update_bus(bus: dict[tuple[str, str], dict[str, Any]], alerts: list[dict[str, Any]], tick_index: int) -> None:
    """
    Merge a list of alerts into an in-memory bus keyed by (symbol, kind).
    Mutates 'bus' in place; keeps:
      - count, first_seen_tick, last_seen_tick
      - max severity across repeats
      - a representative value/threshold pair with max |value-threshold|
      - raw_symbol when sanitization was required (Bug #86 fix)
    """
    if alerts is None:
        return

    # Defensive type coercion: alerts must be an iterable of mapping objects. Bug #63.
    prepared_alerts: list[dict[str, Any]] = []

    if isinstance(alerts, Mapping):
        prepared_alerts.append(deepcopy(dict(alerts)))
    elif isinstance(alerts, str):
        logger.error(
            "notify.update_bus: expected iterable of alert mappings, got string value '%s'",
            alerts,
        )
        return
    else:
        try:
            iterator = iter(alerts)
        except TypeError:
            logger.error(
                "notify.update_bus: alerts payload of type %s is not iterable",
                type(alerts).__name__,
            )
            return

        for idx, entry in enumerate(iterator):
            if entry is None:
                logger.warning(
                    "notify.update_bus: skipping None alert payload at index %d",
                    idx,
                )
                continue
            if not isinstance(entry, Mapping):
                logger.error(
                    "notify.update_bus: skipping alerts[%d] of unsupported type %s",
                    idx,
                    type(entry).__name__,
                )
                continue
            prepared_alerts.append(deepcopy(dict(entry)))

    if not prepared_alerts:
        return

    for a in prepared_alerts:
        raw_symbol = a.get("symbol")
        sym, sym_issue = _normalize_symbol(raw_symbol)
        if sym_issue:
            logger.warning(
                "notify.update_bus.symbol_normalized: original=%r sanitized=%s reason=%s",
                raw_symbol,
                sym,
                sym_issue,
            )

        kind = str(a.get("kind", "")).strip()
        key = (sym, kind)
        ev = bus.get(key)
        tick_context = f"{sym}/{kind}"
        if ev is None:
            prior_tick = 0
        else:
            prior_tick = safe_int(
                ev.get("last_seen_tick"),
                default=0,
                warn=False,
                context=f"notify.last_seen_tick[{tick_context}]",
            )
        tick_value = safe_int(
            tick_index,
            default=prior_tick,
            context=f"notify.tick_index[{tick_context}]",
        )
        if ev is None:
            # FIX Bug #74: Use _normalize_severity to handle None correctly
            bus[key] = {
                "symbol": sym,
                "kind": kind,
                "severity": _normalize_severity(a.get("severity")),
                "message": a.get("message", ""),
                "threshold": deepcopy(a.get("threshold")),
                "value": deepcopy(a.get("value")),
                "count": 1,
                "first_seen_tick": tick_value,
                "last_seen_tick": tick_value,
            }
            if sym_issue:
                bus[key]["raw_symbol"] = "" if raw_symbol is None else str(raw_symbol)
            if a.get("sustainment"):
                bus[key]["sustainment"] = deepcopy(a["sustainment"])
            if a.get("supply"):
                bus[key]["supply"] = deepcopy(a["supply"])
            if a.get("gate"):
                bus[key]["gate"] = deepcopy(a["gate"])
            readiness_payload = a.get("readiness")
            if readiness_payload:
                bus[key]["readiness"] = deepcopy(readiness_payload)
        else:
            ev["count"] += 1
            ev["last_seen_tick"] = tick_value
            # FIX Bug #74: Use _normalize_severity to handle None correctly
            # keep max severity
            severity = _normalize_severity(a.get("severity"))
            if _rank(severity) > _rank(ev.get("severity")):
                ev["severity"] = severity
            if sym_issue and "raw_symbol" not in ev:
                ev["raw_symbol"] = "" if raw_symbol is None else str(raw_symbol)
            if "sustainment" not in ev and a.get("sustainment"):
                ev["sustainment"] = deepcopy(a["sustainment"])
            if "supply" not in ev and a.get("supply"):
                ev["supply"] = deepcopy(a["supply"])
            if "gate" not in ev and a.get("gate"):
                ev["gate"] = deepcopy(a["gate"])
            if "readiness" not in ev and a.get("readiness"):
                ev["readiness"] = deepcopy(a["readiness"])
            # Bug #82 Fix: Keep the largest magnitude distance from threshold as representative
            # Use granular error handling to ensure we always have valid data
            old_mag = _safe_magnitude(ev.get("value"), ev.get("threshold"), context=f"old:{sym}/{kind}")
            new_mag = _safe_magnitude(a.get("value"), a.get("threshold"), context=f"new:{sym}/{kind}")

            # Decision matrix for magnitude update:
            # - Both valid: Compare and update if new > old
            # - Only new valid: Update (fresh data better than corrupt old)
            # - Only old valid OR both invalid: Keep old (stable or no good options)
            if new_mag is not None and old_mag is not None:
                # Both calculations succeeded - compare magnitudes
                if new_mag > old_mag:
                    ev["value"] = deepcopy(a.get("value"))
                    ev["threshold"] = deepcopy(a.get("threshold"))
                # else: old magnitude is larger, keep existing values
            elif new_mag is not None:
                # Only new calculation succeeded - update to fresh data
                ev["value"] = deepcopy(a.get("value"))
                ev["threshold"] = deepcopy(a.get("threshold"))
                logger.warning(
                    "notify.update_bus.old_magnitude_invalid for %s/%s, using new values",
                    sym,
                    kind,
                )
            # else: Keep old values (either old is valid or both failed)

            # Always update message to reflect latest alert state
            if a.get("message"):
                ev["message"] = a.get("message")


def aggregate_alerts(runs: list[dict[str, Any]], *, use_index: bool = False) -> dict[str, Any]:
    """
    Take a list of run outputs (from runtime.loop.run_once) and return a prioritized
    list of deduped events + severity counts.

    Args:
        runs: List of run outputs containing alerts
        use_index: If True, returns AlertIndex for efficient queries (Bug #80 fix).
                   Default False for backward compatibility.

    Returns:
        Dict with keys:
        - "events": List of sorted alert events (or AlertIndex if use_index=True)
        - "counts": Dict of severity counts {"high": n, "medium": m, ...}

    Bug #80 Fix: Set use_index=True to enable O(1) filtered queries instead of O(n) scans.
    """
    bus: dict[tuple[str, str], dict[str, Any]] = {}
    for i, r in enumerate(runs or []):
        update_bus(bus, r.get("alerts", []), tick_index=i)

    events = list(bus.values())

    def magnitude(e: dict[str, Any]) -> float:
        """Calculate magnitude for sorting, using same logic as update_bus (Bug #82 fix)."""
        result = _safe_magnitude(
            e.get("value"),
            e.get("threshold"),
            context=f"sort:{e.get('symbol')}/{e.get('kind')}",
        )
        return result if result is not None else 0.0

    def _safe_last_seen(e: dict[str, Any]) -> int:
        ctx = f"aggregate.last_seen_tick:{e.get('symbol', '?')}/{e.get('kind', '?')}"
        return safe_int(e.get("last_seen_tick"), default=0, warn=False, context=ctx)

    events.sort(
        key=lambda e: (
            _rank(e.get("severity")),
            _safe_last_seen(e),
            magnitude(e),
        ),
        reverse=True,
    )

    counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for e in events:
        # FIX Bug #74: Use _normalize_severity to handle None correctly
        sev = _normalize_severity(e.get("severity"))
        counts[sev] = counts.get(sev, 0) + 1

    # Bug #80 Fix: Optionally return indexed version for efficient queries
    if use_index:
        return {"events": AlertIndex(events), "counts": counts}
    else:
        return {"events": events, "counts": counts}
