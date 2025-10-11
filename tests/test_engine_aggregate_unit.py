"""
Unit tests for optipanel.engine.aggregate.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from optipanel.engine.aggregate import (
    _bundle_to_floats,
    _calculate_risk_penalty,
    _clamp_int,
    _ensure_required_fields,
    build_symbol_snapshot,
)
from optipanel.setups.engine import SetupConfig

# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def base_features_aggregate() -> dict[str, object]:
    """Representative feature payload with timeframe bundles."""
    return {
        "bundles": {
            "1d": {
                "last": 105.0,
                "dma20": 100.0,
                "support": 98.0,
                "resistance": 112.0,
                "rvol": 1.3,
                "rs_strength": 0.4,
                "vwap_diff": 0.02,
            },
            "60m": {
                "last": 103.0,
                "dma20": 99.0,
                "support": 97.0,
                "resistance": 109.0,
                "rvol": 1.1,
                "rs_strength": 0.2,
                "vwap_diff": 0.01,
            },
        },
        "last": 104.0,
        "dma20": 101.0,
        "support": 97.5,
        "resistance": 111.5,
        "rvol": 1.1,
        "rs_strength": 0.25,
        "vwap_diff": 0.015,
    }


@pytest.fixture
def aggregate_stubs(monkeypatch):
    """Patch aggregation dependencies so tests can control behaviour."""
    stubs = SimpleNamespace()
    stubs.setups = {
        "trend_long": 80,
        "trend_short": 40,
        "breakout_up": 70,
        "breakdown_down": 30,
        "exhaustion": 40,
    }
    stubs.units = {"position_size": 100, "risk_exposure": 5000}
    stubs.prob_chips = {"1d": {"bull": 60, "bear": 40}}
    stubs.prob_summary = {"summary": {"bull": 60, "bear": 40}}
    stubs.sustainment = {"sustainability": 55, "fakeout_risk": 25}

    def compute_setups_stub(bundle, config):
        stubs.last_setups_bundle = bundle
        stubs.last_setups_config = config
        return dict(stubs.setups)

    def compute_units_stub(bundle):
        stubs.last_units_bundle = bundle
        return dict(stubs.units)

    def compute_prob_chips_stub(bundles):
        stubs.last_prob_input = deepcopy(bundles)
        return deepcopy(stubs.prob_chips)

    def compute_sustainment_stub(prob_chips):
        stubs.last_sustainment_input = deepcopy(prob_chips)
        return dict(stubs.sustainment)

    def summarize_chips_stub(prob_chips):
        stubs.last_summary_input = deepcopy(prob_chips)
        return dict(stubs.prob_summary)

    monkeypatch.setattr("optipanel.engine.aggregate.compute_setups", compute_setups_stub)
    monkeypatch.setattr("optipanel.engine.aggregate.compute_units", compute_units_stub)
    monkeypatch.setattr("optipanel.engine.aggregate.compute_prob_chips", compute_prob_chips_stub)
    monkeypatch.setattr("optipanel.engine.aggregate.compute_sustainment", compute_sustainment_stub)
    monkeypatch.setattr("optipanel.engine.aggregate.summarize_chips", summarize_chips_stub)

    return stubs


# --------------------------------------------------------------------------- helper tests


def test_clamp_int() -> None:
    assert _clamp_int(Decimal("42.8")) == 43
    assert _clamp_int(Decimal("-5")) == 0
    assert _clamp_int(Decimal("150")) == 100


def test_bundle_to_floats_top_level() -> None:
    bundle = {"score": Decimal("0.85"), "count": 3, "nested": {"value": Decimal("1.25")}}
    converted = _bundle_to_floats(bundle)
    assert isinstance(converted["score"], float)
    assert converted["score"] == 0.85
    assert converted["count"] == 3  # ints remain ints
    # Nested dictionaries are unchanged by the helper (only top-level conversion)
    assert isinstance(converted["nested"]["value"], Decimal)
    assert _bundle_to_floats({}) == {}


def test_calculate_risk_penalty() -> None:
    config = SetupConfig()
    fakeout_threshold = Decimal(str(config.advice_fakeout_risk_max))
    penalty = _calculate_risk_penalty(Decimal("80"), Decimal("30"), fakeout_threshold + Decimal("10"), config)
    assert penalty == Decimal("15")

    assert _calculate_risk_penalty(Decimal("50"), Decimal("60"), Decimal("20"), config) == Decimal("0")

    capped = _calculate_risk_penalty(Decimal("150"), Decimal("0"), Decimal("150"), config)
    assert capped == Decimal("50")


def test_ensure_required_fields_uses_fallback_and_raw() -> None:
    bundle = {"last": Decimal("101")}
    fallback = {"dma20": Decimal("99"), "support": Decimal("95")}
    raw = {"resistance": 110, "rvol": 1.3, "rs_strength": -0.2, "vwap_diff": 0.01}

    _ensure_required_fields(bundle, fallback, raw)

    for key in ("last", "dma20", "support", "resistance", "rvol", "rs_strength", "vwap_diff"):
        assert key in bundle
        assert isinstance(bundle[key], Decimal)


# --------------------------------------------------------------------------- build_symbol_snapshot


def test_build_symbol_snapshot_structure(base_features_aggregate, aggregate_stubs) -> None:
    snapshot = build_symbol_snapshot("AAPL", base_features_aggregate, config=SetupConfig())

    assert snapshot["symbol"] == "AAPL"
    assert snapshot["units"] == aggregate_stubs.units
    assert snapshot["setups"] == aggregate_stubs.setups
    assert snapshot["sustainment"] == aggregate_stubs.sustainment
    assert snapshot["prob_chips"] == aggregate_stubs.prob_chips
    assert snapshot["prob_summary"] == aggregate_stubs.prob_summary

    # Score and advice follow the configured bias (80 vs 40, 70 vs 30) with no penalties.
    assert snapshot["score"] == 90
    assert snapshot["advice"] == "attack"

    # Primary bundle converted to floats for API responses.
    battlefield = snapshot["battlefield_bundle"]
    assert isinstance(battlefield["last"], float)
    assert battlefield["last"] == pytest.approx(105.0)

    # Original features retained as a shallow copy.
    assert snapshot["features"]["bundles"] is base_features_aggregate["bundles"]

    # Dependencies received Decimal-normalised inputs.
    last_bundle = aggregate_stubs.last_setups_bundle
    assert isinstance(last_bundle["last"], Decimal)
    assert last_bundle["last"] == Decimal("105")


def test_build_symbol_snapshot_risk_penalty_applied(base_features_aggregate, aggregate_stubs) -> None:
    config = SetupConfig()

    # Penalised scenario: high exhaustion and fakeout risk.
    # Base bias from trend/breakout yields 95 before penalties.
    aggregate_stubs.setups = {
        "trend_long": 70,
        "trend_short": 20,
        "breakout_up": 70,
        "breakdown_down": 30,
        "exhaustion": 90,
    }
    aggregate_stubs.sustainment = {"sustainability": 35, "fakeout_risk": 80}
    penalised = build_symbol_snapshot("RISK", base_features_aggregate, config)

    # Safe scenario: identical bias but low risk metrics.
    aggregate_stubs.setups = {
        "trend_long": 70,
        "trend_short": 20,
        "breakout_up": 70,
        "breakdown_down": 30,
        "exhaustion": 40,
    }
    aggregate_stubs.sustainment = {"sustainability": 80, "fakeout_risk": 10}
    safe = build_symbol_snapshot("SAFE", base_features_aggregate, config)

    assert penalised["score"] < safe["score"]
    assert penalised["score"] == 78
    assert safe["score"] == 95


def test_build_symbol_snapshot_advice_transitions(base_features_aggregate, aggregate_stubs) -> None:
    config = SetupConfig()

    # Strong bullish signal -> attack
    aggregate_stubs.setups = {
        "trend_long": 85,
        "trend_short": 15,
        "breakout_up": 75,
        "breakdown_down": 25,
        "exhaustion": 40,
    }
    aggregate_stubs.sustainment = {"sustainability": 70, "fakeout_risk": 20}
    assert build_symbol_snapshot("LONG", base_features_aggregate, config)["advice"] == "attack"

    # Strong bearish signal -> defend
    aggregate_stubs.setups = {
        "trend_long": 10,
        "trend_short": 80,
        "breakout_up": 15,
        "breakdown_down": 75,
        "exhaustion": 40,
    }
    aggregate_stubs.sustainment = {"sustainability": 70, "fakeout_risk": 20}
    assert build_symbol_snapshot("SHORT", base_features_aggregate, config)["advice"] == "defend"

    # Moderate/neutral signal -> standby
    aggregate_stubs.setups = {
        "trend_long": 55,
        "trend_short": 45,
        "breakout_up": 50,
        "breakdown_down": 50,
        "exhaustion": 40,
    }
    aggregate_stubs.sustainment = {"sustainability": 70, "fakeout_risk": 20}
    assert build_symbol_snapshot("NEUTRAL", base_features_aggregate, config)["advice"] == "standby"


def test_build_symbol_snapshot_handles_missing_bundles(aggregate_stubs) -> None:
    features = {
        "last": 103.0,
        "dma20": 100.0,
        "support": 97.0,
        "resistance": 110.0,
        "rvol": 1.0,
        "rs_strength": 0.1,
        "vwap_diff": 0.0,
    }
    snapshot = build_symbol_snapshot("FALLBACK", features, config=SetupConfig())

    assert aggregate_stubs.last_setups_bundle["last"] == Decimal("103")
    assert snapshot["battlefield_bundle"]["last"] == pytest.approx(103.0)


def test_build_symbol_snapshot_empty_input(aggregate_stubs) -> None:
    snapshot = build_symbol_snapshot("EMPTY", {})
    assert snapshot["symbol"] == "EMPTY"
    assert 0 <= snapshot["score"] <= 100
    assert snapshot["units"] == aggregate_stubs.units
