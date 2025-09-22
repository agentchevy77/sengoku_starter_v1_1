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
from optipanel.readiness.engine import compute_readiness


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
            if idx == 0:
                lines.append(f"SUPPLY ⇐ {key}: {', '.join(factors)}")
            else:
                lines.append(f"         {key}: {', '.join(factors)}")
    return lines


_TF_CANON = {"15m": "M15", "60m": "H1", "1d": "D"}


def _build_canon_prob(chips: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, int]]:
    canon: dict[str, dict[str, int]] = {}
    if not isinstance(chips, Mapping):
        return canon
    for tf, block in chips.items():
        if tf == "summary" or not isinstance(block, Mapping):
            continue
        key = _TF_CANON.get(str(tf).lower()) or str(tf).upper()
        canon[key] = {k: int(round(float(block[k]))) for k in block if isinstance(block[k], float | int)}
    return canon


def _clamp_line(text: str, width: int) -> str:
    if width <= 0 or len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _extract_bars(features: Mapping[str, Any] | None):
    if not isinstance(features, Mapping):
        return None
    for key in ("bars", "recent_bars", "ohlc"):
        candidate = features.get(key)
        if isinstance(candidate, list):
            return candidate
    return None


def _compute_acceptance(features: Mapping[str, Any] | None) -> tuple[dict[str, dict[str, bool]], str | None]:
    bars = _extract_bars(features)
    if not bars:
        return {}, None

    direction = None
    result = None
    resistance = features.get("resistance") if isinstance(features, Mapping) else None
    support = features.get("support") if isinstance(features, Mapping) else None

    acceptance = {
        "up": {"accepted": False},
        "down": {"accepted": False},
    }

    if resistance is not None:
        res_up = detect_breakout_acceptance(bars, resistance)
        acceptance["up"]["accepted"] = bool(res_up.get("accepted"))
        if res_up["armed"] and res_up["debug"].get("direction") == "up":
            result = res_up
            direction = "UP"

    if support is not None:
        res_down = detect_breakout_acceptance(bars, support)
        acceptance["down"]["accepted"] = bool(res_down.get("accepted"))
        if result is None and res_down["armed"] and res_down["debug"].get("direction") == "down":
            result = res_down
            direction = "DOWN"

    if not result:
        return acceptance, None

    def flag(value: bool) -> str:
        return "Y" if value else "N"

    text = f"ACCEPT   armed={flag(result['armed'])} accepted={flag(result['accepted'])}"
    if direction:
        text += f" dir={direction}"
    return acceptance, text


def _render_acceptance_line(features: Mapping[str, Any] | None) -> str | None:
    _acceptance, line = _compute_acceptance(features)
    return line


def _render_sustainment_lines(
    chips: Mapping[str, Mapping[str, Any]] | None,
    width: int,
) -> tuple[list[str], dict[str, Any], dict[str, dict[str, int]]]:
    canon = _build_canon_prob(chips)
    if not canon:
        sustain = compute_sustainment({})
        return [], sustain, canon
    sustain = compute_sustainment(canon)
    combined = f"SUSTAIN  sustain={sustain['sustainability']:3d} " f"fakeout={sustain['fakeout_risk']:3d}"
    if len(combined) <= width or width <= 0:
        return [combined], sustain, canon
    return (
        [
            f"SUSTAIN  sustain={sustain['sustainability']:3d}",
            f"         fakeout={sustain['fakeout_risk']:3d}",
        ],
        sustain,
        canon,
    )


def _render_readiness_line(
    chips: Mapping[str, Mapping[str, int]] | None,
    sustainment: Mapping[str, Any] | None = None,
    acceptance: Mapping[str, Any] | None = None,
) -> str | None:
    try:
        if not isinstance(chips, Mapping):
            return None

        normalized: dict[str, dict[str, int]] = {}
        for tf, block in chips.items():
            if not isinstance(block, Mapping):
                continue
            sanitized: dict[str, int] = {}
            for key, value in block.items():
                if isinstance(value, int | float):
                    sanitized[str(key)] = int(round(float(value)))
            if sanitized:
                normalized[str(tf)] = sanitized

        sustain = sustainment or compute_sustainment(normalized)
        readiness = compute_readiness(normalized, sustain, acceptance)
        return "READINESS attack={:3d}  defense={:3d}".format(
            int(readiness.get("attack", 0)),
            int(readiness.get("defense", 0)),
        )
    except Exception:
        return None


def render_command_room(run_out: dict[str, Any], width: int = 24, top_n: int = 1) -> str:
    scan = run_out.get("scan", {})
    alerts = run_out.get("alerts", [])
    results = scan.get("results", [])
    advice_counts = scan.get("advice_counts", {})
    top = list(scan.get("top", []))[: max(1, int(top_n))]

    lines: list[str] = []

    def _add(text: str) -> None:
        lines.append(_clamp_line(text, width))

    _add("=== COMMAND ROOM (LIVE) ===")
    _add(
        f"advice: attack={advice_counts.get('attack',0)} "
        f"defend={advice_counts.get('defend',0)} "
        f"standby={advice_counts.get('standby',0)}"
    )
    _add("TOP: " + (", ".join(top) if top else "-"))

    for sym in top:
        snap = _find_snap(results, sym)
        if not snap:
            continue
        score = int(snap.get("score", 0))
        advice = snap.get("advice", "standby")
        _add("")
        _add(f"[{sym}] score={score} advice={advice}")
        features = snap.get("features") if isinstance(snap, Mapping) else None
        bundle = snap.get("battlefield_bundle")
        if isinstance(bundle, Mapping):
            for line in render_battlefield_from_bundle(bundle, width=width).splitlines():
                _add(line)
        else:
            units = snap.get("units", {})
            for line in render_battlefield(units, width=width).splitlines():
                _add(line)

        chips = snap.get("prob_chips")
        acceptance_flags: dict[str, dict[str, bool]] = {}
        accept_line: str | None = None

        if isinstance(chips, Mapping) and chips:
            summary = snap.get("prob_summary")
            if isinstance(summary, Mapping):
                _add("chips(summary) " + _format_chip_block(summary))
            for tf in sorted(chips.keys()):
                block = chips.get(tf)
                if isinstance(block, Mapping):
                    _add(f"chips({tf}) " + _format_chip_block(block))

            recon_blocks = dict(chips)
            if recon_blocks:
                _add(_render_recon_line(recon_blocks))
            sustain_lines, sustain_data, canon_tf = _render_sustainment_lines(chips, width)
            for line in sustain_lines:
                _add(line)
            acceptance_flags, accept_line = _compute_acceptance(features)
            ready_line = _render_readiness_line(
                canon_tf,
                sustainment=sustain_data,
                acceptance=acceptance_flags,
            )
            if ready_line:
                _add(ready_line)
        else:
            acceptance_flags, accept_line = _compute_acceptance(features)
            ready_line = _render_readiness_line({}, acceptance=acceptance_flags)
            if ready_line:
                _add(ready_line)

        micro_rows, micro_by_tf = _micro_rows_for_snap(snap)
        for row in micro_rows:
            _add(row)

        if accept_line:
            _add(accept_line)

        supply_lines = _render_supply_lines(snap.get("setups"), micro_by_tf)
        for row in supply_lines:
            _add(row)

    if alerts:
        counts = Counter(a.get("kind", "?") for a in alerts)
        _add("")
        _add("alerts:")
        for kind in sorted(counts.keys()):
            _add(f"  {kind}: {counts[kind]}")

    return "\n".join(lines)
