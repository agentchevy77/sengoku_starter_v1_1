from optipanel.runtime.loop import run_once
from optipanel.notify.engine import aggregate_alerts

BULL = dict(last=105.0, dma20=100.0, support=101.0, resistance=106.0,
            rvol=1.6, rs_strength=0.30, vwap_diff=0.012)
BEAR = dict(last= 95.0, dma20=100.0, support= 96.0, resistance=100.0,
            rvol=1.5, rs_strength=-0.25, vwap_diff=-0.012)

def _index(events):
    return {(e["symbol"], e["kind"]): e for e in events}

def test_aggregate_alerts_dedupes_and_counts():
    runs = [run_once({"AAA":BULL,"BBB":BEAR}) for _ in range(2)]
    agg = aggregate_alerts(runs)
    assert "events" in agg and "counts" in agg
    idx = _index(agg["events"])
    # We should see repeated conditions with count >= 2 for common alerts
    assert ("AAA","trend_long") in idx and idx[("AAA","trend_long")]["count"] >= 2
    assert ("BBB","breakdown_down") in idx and idx[("BBB","breakdown_down")]["count"] >= 2
    # Severity counts should be non-zero
    assert sum(agg["counts"].values()) >= 2
