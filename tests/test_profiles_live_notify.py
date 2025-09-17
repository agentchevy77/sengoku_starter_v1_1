from optipanel.config.loader import parse_profiles_yaml, parse_features_yaml
from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.runtime.profiles_live import run_profiles_with_provider

PROF_YAML = """
watchlists:
  prime: [AAA]
  secondary: [BBB]
budgets:
  prime: {soft_cap: 10, cooldown: 1, used_lines: [20,5,5], scan_stride_backoff: 2}
  secondary: {soft_cap: 100, cooldown: 1, used_lines: 1}
ui: {width: 20, top_n: 1}
"""

FEAT_YAML = """
AAA: {last: 105.0, dma20: 100.0, support: 101.0, resistance: 106.0, rvol: 1.6, rs_strength: 0.3, vwap_diff: 0.012}
BBB: {last:  95.0, dma20: 100.0, support:  96.0, resistance: 100.0, rvol: 1.5, rs_strength: -0.25, vwap_diff: -0.012}
"""

def test_profiles_live_includes_notify_with_events():
    prof = parse_profiles_yaml(PROF_YAML)
    feats = parse_features_yaml(FEAT_YAML)
    provider = MockFeaturesProvider(feats)

    out = run_profiles_with_provider(prof, provider, ticks=3)
    prime = out["lists"]["prime"]
    sec   = out["lists"]["secondary"]

    assert "notify" in prime and "events" in prime["notify"] and "counts" in prime["notify"]
    assert isinstance(prime["notify"]["events"], list)
    assert isinstance(prime["notify"]["counts"], dict)
    # Since prime scans twice, at least some repeated alert should show count >= 2
    assert any(e.get("count",0) >= 2 for e in prime["notify"]["events"])

    assert "notify" in sec and "events" in sec["notify"] and "counts" in sec["notify"]
    assert len(sec["notify"]["events"]) >= 1
