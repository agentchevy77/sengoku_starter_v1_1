from __future__ import annotations
from typing import Dict, Any, List
from collections import Counter

from optipanel.battlefield.ascii import render_battlefield

def _find_snap(scan_results: List[Dict[str, Any]], symbol: str) -> Dict[str, Any] | None:
    for r in scan_results:
        if r.get("symbol") == symbol:
            return r
    return None

def render_command_room(run_out: Dict[str, Any], width: int = 24, top_n: int = 1) -> str:
    """
    Render a compact ASCII panel for a single run_out produced by runtime.loop.run_once().
    Shows:
      - advice counts (attack/defend/standby)
      - TOP list
      - battlefield bars (TOTAL + indicator lines) for top N symbols
      - alert kind histogram
    Pure; deterministic; no I/O.
    """
    scan = run_out.get("scan", {})
    alerts = run_out.get("alerts", [])
    results = scan.get("results", [])
    advice_counts = scan.get("advice_counts", {})
    top = list(scan.get("top", []))[: max(1, int(top_n))]

    lines: List[str] = []
    lines.append("=== COMMAND ROOM (offline stub) ===")
    lines.append(
        f"advice: attack={advice_counts.get('attack',0)} "
        f"defend={advice_counts.get('defend',0)} "
        f"standby={advice_counts.get('standby',0)}"
    )
    lines.append("TOP: " + (", ".join(top) if top else "-"))

    for sym in top:
        snap = _find_snap(results, sym)
        if not snap:
            continue
        score = int(snap.get("score", 0))
        advice = snap.get("advice", "standby")
        lines.append(f"\n[{sym}] score={score} advice={advice}")
        units = snap.get("units", {})
        lines.append(render_battlefield(units, width=width))

    if alerts:
        counts = Counter(a.get("kind","?") for a in alerts)
        lines.append("\nalerts:")
        for kind in sorted(counts.keys()):
            lines.append(f"  {kind}: {counts[kind]}")

    return "\n".join(lines)
