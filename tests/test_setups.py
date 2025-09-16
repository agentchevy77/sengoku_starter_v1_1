from optipanel.setups.engine import compute_setups

def _check_range(s, keys):
    for k in keys:
        assert k in s, f"missing key {k}"
        assert isinstance(s[k], int)
        assert 0 <= s[k] <= 100

def test_setups_breakout_bullish():
    # Breakout candidate: near resistance, strong RVOL & RS, above 20DMA, above VWAP
    features = dict(
        last=105.0,
        dma20=100.0,
        support=101.0,
        resistance=106.0,    # ~0.95% above last
        rvol=1.6,
        rs_strength=0.30,
        vwap_diff=0.012,     # +1.2% over VWAP
    )
    s = compute_setups(features)
    _check_range(s, [
        "breakout_up","breakdown_down","bounce_up","rejection_down",
        "trend_long","trend_short","exhaustion"
    ])
    assert s["breakout_up"]   >= 80
    assert s["trend_long"]    >= 70
    assert s["breakdown_down"] <= 40
    assert s["rejection_down"] <= 50

def test_setups_breakdown_bearish():
    # Breakdown candidate: support broken/near, weak RS, below 20DMA, below VWAP
    features = dict(
        last=95.0,
        dma20=100.0,
        support=96.0,        # BELOW support -> broken
        resistance=100.0,
        rvol=1.5,
        rs_strength=-0.25,
        vwap_diff=-0.012,    # -1.2% under VWAP
    )
    s = compute_setups(features)
    assert s["breakdown_down"] >= 80
    assert s["trend_short"]    >= 70
    assert s["breakout_up"]    <= 40
    assert s["bounce_up"]      <= 50
