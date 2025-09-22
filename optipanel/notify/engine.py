from __future__ import annotations

from typing import Any

_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 1}


def _rank(s: Any) -> int:
    return _SEV_RANK.get(str(s).lower(), 1)


def update_bus(bus: dict[tuple[str, str], dict[str, Any]], alerts: list[dict[str, Any]], tick_index: int) -> None:
    """
    Merge a list of alerts into an in-memory bus keyed by (symbol, kind).
    Mutates 'bus' in place; keeps:
      - count, first_seen_tick, last_seen_tick
      - max severity across repeats
      - a representative value/threshold pair with max |value-threshold|
    """
    for a in alerts or []:
        sym = str(a.get("symbol", ""))
        kind = str(a.get("kind", ""))
        key = (sym, kind)
        ev = bus.get(key)
        if ev is None:
            bus[key] = {
                "symbol": sym,
                "kind": kind,
                "severity": str(a.get("severity", "info")).lower(),
                "message": a.get("message", ""),
                "threshold": a.get("threshold"),
                "value": a.get("value"),
                "count": 1,
                "first_seen_tick": tick_index,
                "last_seen_tick": tick_index,
            }
            if a.get("sustainment"):
                bus[key]["sustainment"] = a["sustainment"]
            if a.get("supply"):
                bus[key]["supply"] = a["supply"]
            if a.get("gate"):
                bus[key]["gate"] = dict(a["gate"])
        else:
            ev["count"] += 1
            ev["last_seen_tick"] = tick_index
            # keep max severity
            severity = str(a.get("severity", "info")).lower()
            if _rank(severity) > _rank(ev.get("severity")):
                ev["severity"] = severity
            if "sustainment" not in ev and a.get("sustainment"):
                ev["sustainment"] = a["sustainment"]
            if "supply" not in ev and a.get("supply"):
                ev["supply"] = a["supply"]
            if "gate" not in ev and a.get("gate"):
                ev["gate"] = dict(a["gate"])
            # keep the largest magnitude distance from threshold as representative
            try:
                old_mag = abs(float(ev.get("value", 0)) - float(ev.get("threshold", 0)))
                new_mag = abs(float(a.get("value", 0)) - float(a.get("threshold", 0)))
                if new_mag > old_mag:
                    ev["value"] = a.get("value")
                    ev["threshold"] = a.get("threshold")
            except Exception:
                pass


def aggregate_alerts(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Take a list of run outputs (from runtime.loop.run_once) and return a prioritized
    list of deduped events + severity counts.
    """
    bus: dict[tuple[str, str], dict[str, Any]] = {}
    for i, r in enumerate(runs or []):
        update_bus(bus, r.get("alerts", []), tick_index=i)

    events = list(bus.values())

    def magnitude(e: dict[str, Any]) -> float:
        try:
            return abs(float(e.get("value", 0)) - float(e.get("threshold", 0)))
        except Exception:
            return 0.0

    events.sort(key=lambda e: (_rank(e.get("severity")), int(e.get("last_seen_tick", 0)), magnitude(e)), reverse=True)

    counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for e in events:
        sev = str(e.get("severity", "info")).lower()
        counts[sev] = counts.get(sev, 0) + 1

    return {"events": events, "counts": counts}
