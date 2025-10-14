from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_TF_W = {"D": 0.5, "H1": 0.3, "M15": 0.2}


def _get(d: Mapping[str, Any] | None, k: str, default: float = 0.0) -> float:
    if not isinstance(d, Mapping):
        return default
    try:
        v = d.get(k, default)
        return float(v if v is not None else default)
    except Exception:
        return default


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _clip100(x: float) -> int:
    if x < 0:
        return 0
    if x > 100:
        return 100
    return int(round(x))


def _tf_attack_core(tf_block: Mapping[str, Any]) -> float:
    tl = _get(tf_block, "trend_long_prob")
    bou = _get(tf_block, "bounce_up_prob")
    bro = _get(tf_block, "breakout_up_prob")
    return 0.50 * tl + 0.35 * bro + 0.15 * bou


def _tf_defense_core(tf_block: Mapping[str, Any]) -> float:
    ts = _get(tf_block, "trend_short_prob")
    rej = _get(tf_block, "rejection_down_prob")
    brd = _get(tf_block, "breakdown_down_prob")
    return 0.50 * ts + 0.35 * brd + 0.15 * rej


def _combine_by_tf(chips_by_tf: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    attack_sum = 0.0
    defense_sum = 0.0
    weight_sum = 0.0
    per_tf: dict[str, dict[str, float]] = {}
    if isinstance(chips_by_tf, Mapping):
        for tf, weight in _TF_W.items():
            block = chips_by_tf.get(tf) or {}
            atk = _tf_attack_core(block)
            dfn = _tf_defense_core(block)
            per_tf[tf] = {"attack_tf": atk, "defense_tf": dfn}
            attack_sum += weight * atk
            defense_sum += weight * dfn
            weight_sum += weight
    if weight_sum == 0:
        weight_sum = 1.0
    return {
        "attack_core": attack_sum / weight_sum,
        "defense_core": defense_sum / weight_sum,
        "per_tf": per_tf,
    }


def _accept_bias(acceptance: Mapping[str, Any] | None) -> dict[str, int]:
    """Return additive bias (±10/±5) based on acceptance states."""

    bias_long = 0
    bias_short = 0
    if not isinstance(acceptance, Mapping):
        return {"long": 0, "short": 0}

    def _bias_for(state: str) -> int:
        state = state.lower()
        if state == "confirmed":
            return 10
        if state == "armed":
            return 5
        if state == "rejected":
            return -10
        return 0

    long_node = acceptance.get("long")
    short_node = acceptance.get("short")

    if isinstance(long_node, Mapping):
        long_state = str(long_node.get("state", "none"))
    elif isinstance(long_node, str):
        long_state = long_node
    else:
        long_state = str(long_node or "none")

    if isinstance(short_node, Mapping):
        short_state = str(short_node.get("state", "none"))
    elif isinstance(short_node, str):
        short_state = short_node
    else:
        short_state = str(short_node or "none")

    bias_long += _bias_for(long_state)
    bias_short += _bias_for(short_state)

    if short_state.lower() == "confirmed":
        bias_long -= 10
    if long_state.lower() == "confirmed":
        bias_short -= 10

    return {"long": bias_long, "short": bias_short}


def compute_readiness(
    chips_by_tf: Mapping[str, Mapping[str, Any]] | None,
    sustainment: Mapping[str, Any] | None,
    acceptance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    combined = _combine_by_tf(chips_by_tf)
    sustain = _get(sustainment, "sustainability", 50.0)
    fakeout = _get(sustainment, "fakeout_risk", 50.0)

    attack_core = combined["attack_core"]
    defense_core = combined["defense_core"]

    attack = 0.7 * attack_core + 0.3 * sustain
    defense = 0.7 * defense_core + 0.3 * fakeout

    bias = _accept_bias(acceptance)
    attack += bias["long"]
    defense += bias["short"]

    attack_int = _clip100(attack)
    defense_int = _clip100(defense)

    return {
        "attack": attack_int,
        "defense": defense_int,
        "components": {
            "attack_core": _clip100(attack_core),
            "defense_core": _clip100(defense_core),
            "sustainability": _clip100(sustain),
            "fakeout_risk": _clip100(fakeout),
            "accept_bias": bias,
            "per_tf": combined["per_tf"],
        },
    }
