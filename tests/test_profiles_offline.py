import json
from optipanel.config.loader import parse_profiles_yaml, parse_features_yaml
from optipanel.runtime.profiles import run_profiles_offline

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
BBB: {last: 95.0, dma20: 100.0, support: 96.0, resistance: 100.0, rvol: 1.5, rs_strength: -0.25, vwap_diff: -0.012}
"""

def test_run_profiles_offline_produces_panels():
    prof = parse_profiles_yaml(PROF_YAML)
    feats = parse_features_yaml(FEAT_YAML)
    out = run_profiles_offline(prof, feats, ticks=3)
    assert "lists" in out and "prime" in out["lists"] and "secondary" in out["lists"]
    assert out["lists"]["prime"]["scanned_count"] >= 1
    panel = "\n".join(out["lists"]["prime"]["panels"])
    assert "COMMAND ROOM" in panel and "dma20" in panel.lower()
