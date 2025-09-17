from __future__ import annotations
from typing import Dict, Any, List, Tuple

_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 1}
def _rank(s: Any) -> int:
    return _SEV_RANK.get(str(s).lower(), 1)

def update_bus(bus: Dict[Tuple[str,str], Dict[str, Any]],
               alerts: List[Dict[str, Any]],
               tick_index: int) -> None:
    """
    Merge a list of alerts into an in-memory bus keyed by (symbol, kind).
    Mutates 'bus' in place; keeps:
      - count, first_seen_tick, last_seen_tick
      - max severity across repeats
      - a representative value/threshold pair with max |value-threshold|
    """
    for a in alerts or []:
        key = (a.get("symbol"), a.get("kind"))
        ev = bus.get(key)
        if ev is None:
            bus[key] = {
                "symbol": a.get("symbol"),
                "kind": a.get("kind"),
                "severity": str(a.get("severity","info")).lower(),
                "message": a.get("message",""),
                "threshold": a.get("threshold"),
                "value": a.get("value"),
                "count": 1,
                "first_seen_tick": tick_index,
                "last_seen_tick": tick_index,
            }
        else:
            ev["count"] += 1
            ev["last_seen_tick"] = tick_index
            # keep max severity
            if _rank(a.get("severity")) > _rank(ev.get("severity")):
                ev["severity"] = str(a.get("severity","info")).lower()
            # keep the largest magnitude distance from threshold as representative
            try:
                old_mag = abs(float(ev.get("value", 0)) - float(ev.get("threshold", 0)))
                new_mag = abs(float(a.get("value", 0)) - float(a.get("threshold", 0)))
                if new_mag > old_mag:
                    ev["value"] = a.get("value")
                    ev["threshold"] = a.get("threshold")
            except Exception:
                pass

def aggregate_alerts(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Take a list of run outputs (from runtime.loop.run_once) and return a prioritized
    list of deduped events + severity counts.
    """
    bus: Dict[Tuple[str,str], Dict[str, Any]] = {}
    for i, r in enumerate(runs or []):
        update_bus(bus, r.get("alerts", []), tick_index=i)

    events = list(bus.values())

    def magnitude(e: Dict[str, Any]) -> float:
        try:
            return abs(float(e.get("value",0)) - float(e.get("threshold",0)))
        except Exception:
            return 0.0

    events.sort(
        key=lambda e: (_rank(e.get("severity")), int(e.get("last_seen_tick",0)), magnitude(e)),
        reverse=True
    )

    counts = {"high":0,"medium":0,"low":0,"info":0}
    for e in events:
        sev = str(e.get("severity","info")).lower()
        counts[sev] = counts.get(sev,0) + 1

    return {"events": events, "counts": counts}
