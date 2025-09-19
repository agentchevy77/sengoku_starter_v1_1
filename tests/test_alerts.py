from optipanel.alerts.engine import DEFAULT_THRESH, analyze_batch, gen_alerts
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


def _has(alerts, kind):
    return any(a.get("kind") == kind for a in alerts)


def test_bullish_triggers_attack_and_breakout_alerts():
    snap = build_symbol_snapshot("AAA", BULL)
    alerts = gen_alerts(snap, DEFAULT_THRESH)
    assert all(a["symbol"] == "AAA" for a in alerts)
    assert _has(alerts, "score_attack")
    assert _has(alerts, "breakout_up")


def test_bearish_triggers_defend_and_breakdown_alerts():
    snap = build_symbol_snapshot("BBB", BEAR)
    alerts = gen_alerts(snap, DEFAULT_THRESH)
    assert _has(alerts, "score_defend")
    assert _has(alerts, "breakdown_down")


def test_threshold_override_suppresses_specific_alert():
    snap = build_symbol_snapshot("AAA", BULL)
    custom = {**DEFAULT_THRESH, "breakout_up": 200}  # suppress
    alerts = gen_alerts(snap, custom)
    assert not _has(alerts, "breakout_up")
    assert _has(alerts, "score_attack")


def test_analyze_batch_combines_two_symbols():
    s1 = build_symbol_snapshot("AAA", BULL)
    s2 = build_symbol_snapshot("BBB", BEAR)
    out = analyze_batch([s1, s2], DEFAULT_THRESH)
    assert isinstance(out, list) and len(out) >= 2
    kinds = {a["kind"] for a in out}
    assert "score_attack" in kinds and "score_defend" in kinds
    syms = {a["symbol"] for a in out}
    assert "AAA" in syms and "BBB" in syms
