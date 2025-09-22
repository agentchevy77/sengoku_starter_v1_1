"""Supply-line explanations for battlefield front units."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# --- Canonical TFs and synonyms ------------------------------------------------
_TF_ALIASES = {
    "d1": "D1",
    "1d": "D1",
    "day": "D1",
    "daily": "D1",
    "h1": "H1",
    "60m": "H1",
    "1h": "H1",
    "m15": "M15",
    "15m": "M15",
}
_CANON_ORDER = ("D1", "H1", "M15")
_TF_WEIGHT = {"D1": 1.05, "H1": 1.00, "M15": 0.92}

_METRIC_WEIGHTS = {
    "donchian": 1.0,
    "res_clear": 1.0,
    "trend_dma": 0.75,
    "vwap": 1.3,
    "rs": 0.75,
    "rvol": 0.85,
    "support_def": 1.0,
}

# --- Microchip thresholds (tune here; shared across units) ---------------------
POS_T = {  # chip >= threshold means supportive (bullish) for up/long cases
    "donchian": 70,
    "res_clear": 60,
    "trend_dma": 70,
    "vwap": 55,
    "rs": 60,
    "rvol": 60,
    "support_def": 60,
}
NEG_T = {  # chip <= threshold means supportive (bearish) for down/short cases
    "donchian": 35,
    "support_def": 40,
    "trend_dma": 45,
    "vwap": 45,
    "rs": 40,
    # rvol is magnitude-only; do not invert (used in both directions)
}

# Exhaustion (extension + participation)
EXH_POS_T = {"trend_dma": 85, "donchian": 85, "rvol": 70}


# --- Helpers ------------------------------------------------------------------
def _canon_tf(tf: str) -> str:
    t = (tf or "").strip().lower()
    return _TF_ALIASES.get(t, tf.upper())


def _canon_chips_by_tf(src: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for tf, block in (src or {}).items():
        key = _canon_tf(tf)
        if not isinstance(block, Mapping):
            continue
        fixed: dict[str, int] = {}
        for name, val in block.items():
            try:
                iv = int(round(float(val)))
            except Exception:
                iv = 0
            fixed[str(name)] = 0 if iv < 0 else 100 if iv > 100 else iv
        out[key] = fixed
    return out


def _score_pos(chips: Mapping[str, int], chip_name: str, tf: str) -> tuple[float, str] | None:
    """Score positive-direction support: chip >= POS_T."""
    if chip_name not in chips or chip_name not in POS_T:
        return None
    v = chips[chip_name]
    t = POS_T[chip_name]
    if v < t:
        return None
    weight = _METRIC_WEIGHTS.get(chip_name, 1.0)
    score = (v - t) * _TF_WEIGHT.get(tf, 1.0) * weight
    label = f"{chip_name}_{tf}"
    return score, label


def _score_neg(chips: Mapping[str, int], chip_name: str, tf: str) -> tuple[float, str] | None:
    """Score negative-direction support: chip <= NEG_T."""
    if chip_name not in chips or chip_name not in NEG_T:
        return None
    v = chips[chip_name]
    t = NEG_T[chip_name]
    if v > t:
        return None
    weight = _METRIC_WEIGHTS.get(chip_name, 1.0)
    score = (t - v) * _TF_WEIGHT.get(tf, 1.0) * weight
    label = f"{chip_name}_low_{tf}"
    return score, label


def _top_k(cands: Iterable[tuple[float, str]], k: int) -> list[str]:
    selected: list[str] = []
    seen_metrics: set[str] = set()
    for _, label in sorted(cands, key=lambda x: (-x[0], x[1])):
        metric_key = label.split("_", 1)[0]
        if metric_key in seen_metrics:
            continue
        selected.append(label)
        seen_metrics.add(metric_key)
        if len(selected) >= k:
            break
    return selected


# --- Unit-specific collectors --------------------------------------------------
def _collect_breakout_up(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name in ("donchian", "res_clear", "rvol", "rs", "vwap", "trend_dma"):
            sc = _score_pos(c, name, tf)
            if sc:
                cands.append(sc)
    return _top_k(cands, 3)


def _collect_breakdown_down(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name in ("donchian", "support_def", "trend_dma", "vwap", "rs"):
            sc = _score_neg(c, name, tf)
            if sc:
                cands.append(sc)
        sc_rv = _score_pos(c, "rvol", tf)
        if sc_rv:
            cands.append(sc_rv)
    return _top_k(cands, 3)


def _collect_bounce_up(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name in ("support_def", "vwap", "rvol", "trend_dma", "rs"):
            sc = _score_pos(c, name, tf)
            if sc:
                cands.append(sc)
        sc_low = _score_neg(c, "donchian", tf)
        if sc_low:
            cands.append(sc_low)
    return _top_k(cands, 3)


def _collect_rejection_down(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        sc_res = _score_pos(c, "res_clear", tf)
        if sc_res:
            cands.append(sc_res)
        for name in ("vwap", "rs", "trend_dma"):
            sc_low = _score_neg(c, name, tf)
            if sc_low:
                cands.append(sc_low)
        sc_rv = _score_pos(c, "rvol", tf)
        if sc_rv:
            cands.append(sc_rv)
        sc_top = _score_pos(c, "donchian", tf)
        if sc_top:
            cands.append(sc_top)
    return _top_k(cands, 3)


def _collect_trend_long(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name in ("trend_dma", "rs", "vwap", "donchian", "rvol", "support_def"):
            sc = _score_pos(c, name, tf)
            if sc:
                cands.append(sc)
    return _top_k(cands, 3)


def _collect_trend_short(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name in ("trend_dma", "rs", "vwap", "donchian"):
            sc_low = _score_neg(c, name, tf)
            if sc_low:
                cands.append(sc_low)
        sc_rv = _score_pos(c, "rvol", tf)
        if sc_rv:
            cands.append(sc_rv)
    return _top_k(cands, 3)


def _collect_exhaustion(chips_by_tf: dict[str, dict[str, int]]) -> list[str]:
    cands: list[tuple[float, str]] = []
    for tf in _CANON_ORDER:
        c = chips_by_tf.get(tf, {})
        for name, th in EXH_POS_T.items():
            v = c.get(name)
            if v is None:
                continue
            if v >= th:
                score = (v - th) * _TF_WEIGHT.get(tf, 1.0)
                cands.append((score, f"{name}_{tf}"))
    return _top_k(cands, 3)


_COLLECTORS = {
    "breakout_up": _collect_breakout_up,
    "breakdown_down": _collect_breakdown_down,
    "bounce_up": _collect_bounce_up,
    "rejection_down": _collect_rejection_down,
    "trend_long": _collect_trend_long,
    "trend_short": _collect_trend_short,
    "exhaustion": _collect_exhaustion,
}


def explain_supply(
    front_units: Mapping[str, int | float] | None,
    chips_by_tf: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, list[str]]:
    """Return supply-line explanations per front unit.

    Output lists are capped at three labels, sorted by margin over threshold with a
    D1 > H1 > M15 weighting.
    """

    canon = _canon_chips_by_tf(chips_by_tf)
    out: dict[str, list[str]] = {}
    for unit, _ in (front_units or {}).items():
        collector = _COLLECTORS.get(unit)
        if collector:
            out[unit] = collector(canon)
    return out


__all__ = ["explain_supply"]
