from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from optipanel.battlefield.supply import explain_supply
from optipanel.chips.aggregate import (
    aggregate_chips,
    compute_sustainment,
    recon_score,
    summarize_chips,
)
from optipanel.chips.compute import compute_chips_by_tf
from optipanel.chips.runtime import chips_by_tf_for_snapshot
from optipanel.readiness import compute_readiness
from optipanel.recon.gating import compute_gate_for_snapshot
from optipanel.setups.engine import compute_setups

try:  # prefer shared helper if available
    from optipanel.chips.runtime import microchips_by_tf_for_snapshot as _micro_for_snapshot
except Exception:  # pragma: no cover
    from optipanel.chips.micro import (
        compute_microchips_daily,
        compute_microchips_h60,
        compute_microchips_m15,
    )

    def _micro_for_snapshot(snapshot: Mapping[str, Any]) -> dict[str, dict[str, int]]:
        bundles: dict[str, Any] = {}
        base = {}
        if isinstance(snapshot, Mapping):
            features_top = snapshot.get("features_top") or snapshot.get("features") or {}
            if isinstance(features_top, Mapping):
                base = dict(features_top)
            b = snapshot.get("bundles")
            if isinstance(b, Mapping):
                bundles = dict(b)

        def _pick(key: str) -> Mapping[str, Any]:
            data = bundles.get(key) if isinstance(bundles, Mapping) else None
            return data if isinstance(data, Mapping) else base

        return {
            "M15": compute_microchips_m15(dict(_pick("15m"))),
            "H1": compute_microchips_h60(dict(_pick("60m"))),
            "D": compute_microchips_daily(dict(_pick("1d"))),
        }


def _index_snaps(snaps: Iterable[Mapping[str, Any]] | None) -> dict[str, Mapping[str, Any]]:
    idx: dict[str, Mapping[str, Any]] = {}
    for snap in snaps or []:
        if not isinstance(snap, Mapping):
            continue
        sym = snap.get("symbol") or snap.get("sym") or snap.get("ticker")
        if isinstance(sym, str) and sym:
            idx[sym] = snap
    return idx


def enrich_alerts_with_supply_sustain(
    snaps: Iterable[Mapping[str, Any]] | None,
    alerts: list[dict[str, Any]] | None,
    *,
    include_supply: bool = False,
    include_sustain: bool = True,
    include_readiness: bool = False,
) -> list[dict[str, Any]]:
    """Attach sustainment (and optional supply) to alert payloads."""

    if not alerts:
        return alerts or []

    snap_idx = _index_snaps(snaps)
    sustain_cache: dict[str, dict[str, Any]] = {}
    supply_cache: dict[str, dict[str, Any]] = {}
    readiness_cache: dict[str, dict[str, int]] = {}
    enriched: list[dict[str, Any]] = []

    for alert in alerts:
        if not isinstance(alert, Mapping):
            continue
        payload = dict(alert)
        sym = payload.get("symbol") or payload.get("sym") or payload.get("ticker")
        snap = snap_idx.get(str(sym)) if isinstance(sym, str) else None
        prob_tf: dict[str, dict[str, Any]] | None = None

        if include_sustain and sym and snap:
            sustain = sustain_cache.get(sym)
            if sustain is None:
                prob_tf = chips_by_tf_for_snapshot(snap)
                sustain = compute_sustainment(prob_tf)
                sustain_cache[sym] = sustain
            payload.setdefault(
                "sustainment",
                {
                    "sustainability": int(sustain.get("sustainability", 50)),
                    "fakeout_risk": int(sustain.get("fakeout_risk", 50)),
                },
            )
        else:
            sustain = None

        if include_supply and sym and snap:
            supply = supply_cache.get(sym)
            if supply is None:
                front_units = snap.get("setups")
                if not isinstance(front_units, Mapping):
                    feats = snap.get("features_top") or snap.get("features") or {}
                    front_units = compute_setups(dict(feats) if isinstance(feats, Mapping) else {})
                micro_by_tf = _micro_for_snapshot(snap)
                supply = explain_supply(front_units or {}, micro_by_tf) or {}
                supply_cache[sym] = supply
            if supply:
                payload.setdefault("supply", supply)

        if include_readiness and sym and snap:
            readiness = readiness_cache.get(sym)
            if readiness is None:
                if prob_tf is None:
                    prob_tf = chips_by_tf_for_snapshot(snap)
                sustain_src = sustain or compute_sustainment(prob_tf)
                readiness_data = compute_readiness(prob_tf, sustain_src, acceptance=None)
                readiness = {
                    "attack": readiness_data["attack"],
                    "defense": readiness_data["defense"],
                }
                readiness_cache[sym] = readiness
            payload.setdefault("readiness", readiness)

        enriched.append(payload)

    return enriched


def build_recon_entry(
    features: Mapping[str, Any],
    *,
    mode: str = "prob",
    include_supply: bool = False,
    include_summary: bool = False,
) -> dict[str, Any]:
    """Construct a recon payload suitable for CLI/notify usage."""

    canonical_tf = compute_chips_by_tf(dict(features), mode="prob")
    sustain = compute_sustainment(canonical_tf)
    agg = aggregate_chips(canonical_tf)

    entry: dict[str, Any] = {
        "recon": recon_score(agg),
        "agg": agg,
        "tf": canonical_tf,
        "mode": mode,
        "sustainment": {
            "sustainability": int(sustain.get("sustainability", 50)),
            "fakeout_risk": int(sustain.get("fakeout_risk", 50)),
        },
    }

    acceptance = None
    raw_accept = features.get("acceptance") if isinstance(features, Mapping) else None
    if isinstance(raw_accept, Mapping):
        acceptance = {
            side: {"accepted": bool(data.get("accepted"))}
            for side, data in raw_accept.items()
            if isinstance(data, Mapping)
        }

    readiness_data = compute_readiness(
        canonical_tf,
        sustainment=sustain,
        acceptance=acceptance,
    )
    entry["readiness"] = {
        "attack": readiness_data["attack"],
        "defense": readiness_data["defense"],
        "components": readiness_data.get("components", {}),
    }

    if mode.lower() == "micro":
        entry["tf_scout"] = compute_chips_by_tf(dict(features), mode="micro")

    if include_summary:
        entry["chips_summary"] = summarize_chips(canonical_tf)

    if include_supply:
        front_units = compute_setups(dict(features))
        micro_by_tf = _micro_for_snapshot({"features": features})
        supply = explain_supply(front_units, micro_by_tf)
        if supply:
            entry["supply"] = supply

    return entry


def compute_chips_by_tf_for_features(features: Mapping[str, Any], *, mode: str = "prob") -> dict[str, dict[str, int]]:
    """Helper to convert raw feature dict into per-timeframe chips."""

    return compute_chips_by_tf(dict(features), mode=mode)


def enrich_alerts_with_gate(
    snaps: Iterable[Mapping[str, Any]],
    alerts: list[dict[str, Any]],
    *,
    require_acceptance: bool = False,
    ready_min: int = 65,
    armed_floor: int = 50,
) -> list[dict[str, Any]]:
    snap_by_sym: dict[str, Mapping[str, Any]] = {}
    for s in snaps or []:
        sym = s.get("symbol")
        if isinstance(sym, str):
            snap_by_sym[sym] = s

    enriched: list[dict[str, Any]] = []
    for alert in alerts:
        sym = alert.get("symbol")
        snap = snap_by_sym.get(sym, {})
        gate = compute_gate_for_snapshot(snap, ready_min=ready_min, armed_floor=armed_floor)
        out = dict(alert)
        out["gate"] = {
            "accepted": gate["accepted"],
            "readiness": gate["readiness"],
            "state": gate["state"],
        }
        if require_acceptance and gate["state"] != "go":
            continue
        enriched.append(out)
    return enriched
