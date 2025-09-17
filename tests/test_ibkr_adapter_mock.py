from optipanel.runtime.loop import run_once, run_once_with
from optipanel.adapters.ibkr import MockFeaturesProvider

BULL = dict(last=105.0, dma20=100.0, support=101.0, resistance=106.0,
            rvol=1.6, rs_strength=0.30, vwap_diff=0.012)
BEAR = dict(last=95.0, dma20=100.0, support=96.0, resistance=100.0,
            rvol=1.5, rs_strength=-0.25, vwap_diff=-0.012)

def _kind_set(alerts):
    return {(a.get("symbol"), a.get("kind")) for a in alerts}

def test_mock_provider_matches_direct_features():
    direct = run_once({"AAA": BULL, "BBB": BEAR})
    prov = MockFeaturesProvider({"AAA": BULL, "BBB": BEAR})
    via_provider = run_once_with(prov, ["AAA","BBB"])

    # Compare core structures
    assert isinstance(via_provider, dict) and "scan" in via_provider and "alerts" in via_provider

    # Top ranking should match (same features)
    assert direct["scan"]["top"] == via_provider["scan"]["top"]

    # Compare alert kinds per symbol (order-independent)
    assert _kind_set(direct["alerts"]) == _kind_set(via_provider["alerts"])

def test_mock_provider_allows_update():
    prov = MockFeaturesProvider({"AAA": BULL})
    out1 = run_once_with(prov, ["AAA"])
    assert out1["scan"]["results"][0]["symbol"] == "AAA"

    # Update AAA to bearish and ensure advice changes accordingly
    prov.set("AAA", BEAR)
    out2 = run_once_with(prov, ["AAA"])
    r = out2["scan"]["results"][0]
    assert r["symbol"] == "AAA"
    assert r["advice"] in ("defend", "standby")
