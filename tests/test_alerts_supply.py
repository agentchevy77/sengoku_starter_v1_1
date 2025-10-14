from __future__ import annotations

from optipanel.alerts.engine import DEFAULT_THRESH, analyze_batch, analyze_batch_with_supply
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.recon.enrich import enrich_alerts_with_supply_sustain

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


def _has_supply(alerts, symbol):
    return any(a.get("symbol") == symbol and a.get("supply") for a in alerts)


def test_alerts_include_supply_when_enabled(monkeypatch):
    monkeypatch.setenv("SENGOKU_ALERTS_INCLUDE_SUPPLY", "1")
    s1 = build_symbol_snapshot("AAA", BULL)
    s2 = build_symbol_snapshot("BBB", BEAR)
    out = analyze_batch_with_supply([s1, s2], thresholds=DEFAULT_THRESH)
    assert _has_supply(out, "AAA") or _has_supply(out, "BBB")


def test_alerts_do_not_include_supply_when_disabled(monkeypatch):
    monkeypatch.delenv("SENGOKU_ALERTS_INCLUDE_SUPPLY", raising=False)
    s1 = build_symbol_snapshot("AAA", BULL)
    out = analyze_batch_with_supply([s1], thresholds=DEFAULT_THRESH, include_supply=False)
    assert all("supply" not in a for a in out)


def test_enrich_adds_sustainment_and_supply_optin():
    snaps = [
        build_symbol_snapshot("AAA", BULL),
        build_symbol_snapshot("BBB", BEAR),
    ]
    # ensure enrichment has feature context similar to CLI/notify paths
    for snap, feats in zip(snaps, (BULL, BEAR), strict=True):
        snap["features"] = dict(feats)

    alerts = analyze_batch(snaps, DEFAULT_THRESH)
    assert all("sustainment" not in a and "supply" not in a for a in alerts)

    enriched = enrich_alerts_with_supply_sustain(
        snaps,
        alerts,
        include_supply=True,
        include_sustain=True,
    )

    assert all("sustainment" in a for a in enriched)
    assert any(a.get("symbol") == "AAA" and a.get("supply") for a in enriched)


def test_alerts_include_readiness_when_enabled(monkeypatch):
    monkeypatch.setenv("SENGOKU_ALERTS_INCLUDE_READINESS", "1")
    snap = build_symbol_snapshot("AAA", BULL)
    snap["features"] = dict(BULL)
    out = analyze_batch_with_supply([snap], thresholds=DEFAULT_THRESH, include_supply=False)
    assert any("readiness" in alert for alert in out)
    ready = next(alert["readiness"] for alert in out if "readiness" in alert)
    assert ready["attack"] >= 0 and ready["defense"] >= 0
