from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from optipanel.battlefield.supply import explain_supply
from optipanel.chips.aggregate import compute_microchips
from optipanel.chips.daily import compute_daily_microchips
from optipanel.chips.h60 import compute_h60_microchips
from optipanel.chips.m15 import compute_m15_microchips
from optipanel.chips.prob_tf import (
    compute_probchips_daily,
    compute_probchips_h60,
    compute_probchips_m15,
)

_ALIAS_TO_CANON = {
    "15m": "M15",
    "m15": "M15",
    "M15": "M15",
    "60m": "H1",
    "1h": "H1",
    "h1": "H1",
    "H1": "H1",
    "1d": "D",
    "d1": "D",
    "day": "D",
    "daily": "D",
    "D": "D",
}

_MICRO_FUNCS = {
    "M15": compute_m15_microchips,
    "H1": compute_h60_microchips,
    "D": compute_daily_microchips,
}

_PROB_FUNCS = {
    "M15": compute_probchips_m15,
    "H1": compute_probchips_h60,
    "D": compute_probchips_daily,
}


def _canon(tf: str) -> str | None:
    return _ALIAS_TO_CANON.get(str(tf), None)


def _base_features(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    features = snapshot.get("features") if isinstance(snapshot, Mapping) else None
    if isinstance(features, Mapping):
        return dict(features)
    bundle = snapshot.get("battlefield_bundle") if isinstance(snapshot, Mapping) else None
    if isinstance(bundle, Mapping):
        return dict(bundle)
    return {}


def _bundle_map(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    features = snapshot.get("features") if isinstance(snapshot, Mapping) else None
    bundles = features.get("bundles") if isinstance(features, Mapping) else None
    out: dict[str, Mapping[str, Any]] = {}
    if not isinstance(bundles, Mapping):
        return out
    for tf, data in bundles.items():
        canon = _canon(tf)
        if canon and isinstance(data, Mapping):
            out[canon] = data
    return out


def microchips_by_tf_for_snapshot(snapshot: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    base = _base_features(snapshot)
    bundles = _bundle_map(snapshot)
    out: dict[str, dict[str, int]] = {}
    for canon, func in _MICRO_FUNCS.items():
        src = bundles.get(canon, base)
        try:
            out[canon] = func(dict(src))
        except Exception:
            out[canon] = {}
    return out


def chips_by_tf_for_snapshot(snapshot: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    base = _base_features(snapshot)
    bundles = _bundle_map(snapshot)
    out: dict[str, dict[str, int]] = {}
    for canon, func in _PROB_FUNCS.items():
        src = bundles.get(canon, base)
        try:
            out[canon] = func(src, base)
        except Exception:
            out[canon] = {}
    return out


def supply_for_snapshot(snapshot: Mapping[str, Any]) -> dict[str, list[str]]:
    setups = snapshot.get("setups") if isinstance(snapshot, Mapping) else None
    if not isinstance(setups, Mapping):
        return {}
    chips = chips_by_tf_for_snapshot(snapshot)
    return explain_supply(setups, chips) or {}


def enrich_features_with_chips(features: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(features, Mapping):
        return {}

    enriched: dict[str, dict[str, Any]] = {}
    for symbol, data in features.items():
        base = dict(data) if isinstance(data, Mapping) else {}
        base.setdefault("microchips", compute_microchips(base))
        enriched[str(symbol)] = base
    return enriched
