from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any

from optipanel.acceptance.engine import detect_breakout_acceptance
from optipanel.battlefield import explain_supply
from optipanel.battlefield.ascii import render_battlefield, render_battlefield_from_bundle
from optipanel.chips.aggregate import aggregate_chips, compute_sustainment, recon_score
from optipanel.chips.micro import (
    compute_microchips_daily,
    compute_microchips_h60,
    compute_microchips_m15,
)


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
        if isinstance(value, float | int):
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


def _fmt_micro_row(label: str, block: Mapping[str, int]) -> str:
    keys = ("donchian", "trend_dma", "support_def", "res_clear", "rvol", "rs", "vwap")
    parts = [f"{k} {int(block.get(k, 0)):3d}" for k in keys]
    return f"micro {label:<3} " + " | ".join(parts)


_MICRO_SPECS: tuple[tuple[str, str, Callable[[dict[str, Any]], dict[str, int]]], ...] = (
    ("M15", "15m", compute_microchips_m15),
    ("H1", "60m", compute_microchips_h60),
    ("D1", "1d", compute_microchips_daily),
)


def _micro_rows_for_snap(snap: Mapping[str, Any]) -> tuple[list[str], dict[str, dict[str, int]]]:
    features = snap.get("features") if isinstance(snap, Mapping) else None
    if not isinstance(features, Mapping):
        bundle = snap.get("battlefield_bundle") if isinstance(snap, Mapping) else None
        if isinstance(bundle, Mapping):
            features = bundle
    if not isinstance(features, Mapping):
        return [], {}

    bundles = features.get("bundles") if isinstance(features, Mapping) else None
    rows: list[str] = []
    chips_by_tf: dict[str, dict[str, int]] = {}

    for canon_tf, bundle_key, compute in _MICRO_SPECS:
        source: Mapping[str, Any] | None = None
        if isinstance(bundles, Mapping):
            cand = bundles.get(bundle_key)
            if isinstance(cand, Mapping):
                source = cand
        if source is None:
            source = features
        try:
            micro = compute(dict(source))
        except Exception:
            micro = {}
        rows.append(_fmt_micro_row(canon_tf, micro))
        chips_by_tf[canon_tf] = micro

    return rows, chips_by_tf


def _render_supply_lines(
    front_units: Mapping[str, Any] | None,
    micro_by_tf: Mapping[str, Mapping[str, int]] | None,
) -> list[str]:
    if not front_units or not micro_by_tf:
        return []
    supply = explain_supply(front_units, micro_by_tf)
    if not supply:
        return []
    order = (
        "breakout_up",
        "trend_long",
        "breakdown_down",
        "trend_short",
        "bounce_up",
        "rejection_down",
        "exhaustion",
    )
    lines: list[str] = []
    for idx, key in enumerate(order):
        factors = supply.get(key)
        if factors:
            prefix = "SUPPLY" if idx == 0 else ""
            lines.append(f"{prefix:<9s}{key:<13s} ⇐ {', '.join(factors)}")
    return lines


_TF_CANON = {"15m": "M15", "60m": "H1", "1d": "D"}


def _extract_bars(features: Mapping[str, Any] | None):
    if not isinstance(features, Mapping):
        return None
    for key in ("bars", "recent_bars", "ohlc"):
        candidate = features.get(key)
        if isinstance(candidate, list):
            return candidate
    return None


def _render_acceptance_line(features: Mapping[str, Any] | None) -> str | None:
    bars = _extract_bars(features)
    if not bars:
        return None

    direction = None
    result = None
    resistance = features.get("resistance") if isinstance(features, Mapping) else None
    support = features.get("support") if isinstance(features, Mapping) else None

    if resistance is not None:
        res_up = detect_breakout_acceptance(bars, resistance)
        if res_up["armed"] and res_up["debug"].get("direction") == "up":
            result = res_up
            direction = "UP"

    if result is None and support is not None:
        res_down = detect_breakout_acceptance(bars, support)
        if res_down["armed"] and res_down["debug"].get("direction") == "down":
            result = res_down
            direction = "DOWN"

    if not result:
        return None

    def flag(value: bool) -> str:
        return "Y" if value else "N"

    text = f"ACCEPT   armed={flag(result['armed'])} accepted={flag(result['accepted'])}"
    if direction:
        text += f" dir={direction}"
    return text


def _render_sustainment_line(chips: Mapping[str, Mapping[str, Any]] | None) -> str | None:
    if not isinstance(chips, Mapping):
        return None
    canon: dict[str, dict[str, int]] = {}
    for tf, block in chips.items():
        if tf == "summary" or not isinstance(block, Mapping):
            continue
        key = _TF_CANON.get(str(tf).lower()) or str(tf).upper()
        canon[key] = {k: int(round(float(block[k]))) for k in block if isinstance(block[k], float | int)}
    if not canon:
        return None
    sustain = compute_sustainment(canon)
    return f"SUSTAIN  sustain={sustain['sustainability']:3d}  fakeout={sustain['fakeout_risk']:3d}"


def render_command_room(run_out: dict[str, Any], width: int = 24, top_n: int = 1) -> str:
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
            summary = snap.get("prob_summary")
            if isinstance(summary, Mapping):
                lines.append("chips(summary) " + _format_chip_block(summary))
            for tf in sorted(chips.keys()):
                block = chips.get(tf)
                if isinstance(block, Mapping):
                    lines.append(f"chips({tf}) " + _format_chip_block(block))

            recon_blocks = dict(chips)
            if recon_blocks:
                lines.append(_render_recon_line(recon_blocks))
            sustain_line = _render_sustainment_line(chips)
            if sustain_line:
                lines.append(sustain_line)

        features = snap.get("features") if isinstance(snap, Mapping) else None
        micro_rows, micro_by_tf = _micro_rows_for_snap(snap)
        for row in micro_rows:
            lines.append(row)

        accept_line = _render_acceptance_line(features)
        if accept_line:
            lines.append(accept_line)

        supply_lines = _render_supply_lines(snap.get("setups"), micro_by_tf)
        for row in supply_lines:
            lines.append(row)

    if alerts:
        counts = Counter(a.get("kind", "?") for a in alerts)
        lines.append("\nalerts:")
        for kind in sorted(counts.keys()):
            lines.append(f"  {kind}: {counts[kind]}")

    return "\n".join(lines)
