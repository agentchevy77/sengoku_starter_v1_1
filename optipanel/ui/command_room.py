from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from optipanel.battlefield.ascii import render_battlefield, render_battlefield_from_bundle
from optipanel.chips.aggregate import aggregate_chips, recon_score


def _find_snap(scan_results: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    for r in scan_results:
        if r.get("symbol") == symbol:
            return r
    return None


def _format_chip_block(chips: Mapping[str, Any]) -> str:
    order = (
        ("breakout_up", "brkU"),
        ("breakdown_down", "brkD"),
        ("bounce_up", "bUp"),
        ("rejection_down", "rejD"),
        ("trend_long", "trL"),
        ("trend_short", "trS"),
        ("fakeout", "fake"),
    )
    parts: list[str] = []
    for key, label in order:
        value = chips.get(key)
        if isinstance(value, int):
            parts.append(f"{label}:{value:02d}")
        elif isinstance(value, float | int):
            parts.append(f"{label}:{int(round(float(value))):02d}")
    return " ".join(parts)


def _sanitize_chip_block(block: Mapping[str, Any]) -> dict[str, int]:
    sanitized: dict[str, int] = {}
    for name, value in block.items():
        if isinstance(value, int | float):
            sanitized[str(name)] = int(round(float(value)))
    return sanitized


def _render_recon_line(chips_by_tf: Mapping[str, Any]) -> str:
    usable: dict[str, dict[str, int]] = {}
    for tf, block in chips_by_tf.items():
        if isinstance(block, Mapping):
            sanitized = _sanitize_chip_block(block)
            if sanitized:
                usable[str(tf)] = sanitized
    if not usable:
        return "SCOUT     recon [  0]"
    try:
        aggregated = aggregate_chips(usable)
        score = recon_score(aggregated)
    except Exception:
        return "SCOUT     recon [  0]"
    return f"SCOUT     recon [{score:3d}]"


def render_command_room(run_out: dict[str, Any], width: int = 24, top_n: int = 1) -> str:
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

    lines: list[str] = []
    lines.append("=== COMMAND ROOM (LIVE) ===")
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
        bundle = snap.get("battlefield_bundle")
        if isinstance(bundle, Mapping):
            lines.append(render_battlefield_from_bundle(bundle, width=width))
        else:
            units = snap.get("units", {})
            lines.append(render_battlefield(units, width=width))

        chips = snap.get("prob_chips")
        if isinstance(chips, Mapping) and chips:
            summary = chips.get("summary")
            if isinstance(summary, Mapping):
                lines.append("chips(summary) " + _format_chip_block(summary))
            for tf in sorted(k for k in chips if k != "summary"):
                block = chips.get(tf)
                if isinstance(block, Mapping):
                    lines.append(f"chips({tf}) " + _format_chip_block(block))

            recon_blocks = {tf: block for tf, block in chips.items() if tf != "summary"}
            if recon_blocks:
                lines.append(_render_recon_line(recon_blocks))

    if alerts:
        counts = Counter(a.get("kind", "?") for a in alerts)
        lines.append("\nalerts:")
        for kind in sorted(counts.keys()):
            lines.append(f"  {kind}: {counts[kind]}")

    return "\n".join(lines)
