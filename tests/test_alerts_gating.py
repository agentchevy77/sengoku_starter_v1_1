from __future__ import annotations

from optipanel.alerts.engine import analyze_batch_with_gate
from optipanel.engine.aggregate import build_symbol_snapshot

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}
BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 1.5,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
}


def _snaps():
    return [
        build_symbol_snapshot("AAA", BULL),
        build_symbol_snapshot("BBB", BEAR),
    ]


def test_gating_attaches_gate_block():
    out = analyze_batch_with_gate(_snaps(), include_supply=False)
    alerts = out.get("alerts", [])
    assert alerts, "alerts produced"
    for alert in alerts:
        gate = alert.get("gate")
        assert isinstance(gate, dict)
        assert {"state", "readiness", "accepted"} <= set(gate)


def test_gating_can_filter_when_required():
    out = analyze_batch_with_gate(_snaps(), require_acceptance=True, ready_min=90)
    alerts = out.get("alerts", [])
    assert isinstance(alerts, list)
