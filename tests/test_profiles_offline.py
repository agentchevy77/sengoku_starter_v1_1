from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
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
AAA:
  last: 105.0
  dma20: 100.0
  support: 101.0
  resistance: 106.0
  rvol: 1.6
  rs_strength: 0.3
  vwap_diff: 0.012
  bundles:
    15m:
      last: 104.4
      dma20: 102.8
      support: 101.2
      resistance: 105.9
      rvol: 1.3
      rs_strength: 0.24
      vwap_diff: 0.009
      donchian_pos: 0.86
      obv_slope: 0.61
      chaikin_ad: 0.53
      clv: 0.47
      avwap_diff: 0.015
      vwap_confluence: 0.64
    60m:
      last: 104.8
      dma20: 103.4
      support: 101.5
      resistance: 106.2
      rvol: 1.4
      rs_strength: 0.27
      vwap_diff: 0.010
      donchian_pos: 0.82
      obv_slope: 0.58
      chaikin_ad: 0.49
      clv: 0.45
      avwap_diff: 0.013
      vwap_confluence: 0.66
BBB:
  last: 95.0
  dma20: 100.0
  support: 96.0
  resistance: 100.0
  rvol: 1.5
  rs_strength: -0.25
  vwap_diff: -0.012
  bundles:
    15m:
      last: 94.2
      dma20: 97.1
      support: 95.0
      resistance: 98.6
      rvol: 0.92
      rs_strength: -0.20
      vwap_diff: -0.010
      donchian_pos: 0.28
      obv_slope: -0.39
      chaikin_ad: -0.33
      clv: -0.30
      avwap_diff: -0.012
      vwap_confluence: 0.42
    60m:
      last: 94.6
      dma20: 97.8
      support: 95.4
      resistance: 99.2
      rvol: 0.95
      rs_strength: -0.22
      vwap_diff: -0.011
      donchian_pos: 0.32
      obv_slope: -0.36
      chaikin_ad: -0.29
      clv: -0.27
      avwap_diff: -0.010
      vwap_confluence: 0.44
"""


def test_run_profiles_offline_produces_panels():
    prof = parse_profiles_yaml(PROF_YAML)
    feats = parse_features_yaml(FEAT_YAML)
    out = run_profiles_offline(prof, feats, ticks=3)
    assert "lists" in out and "prime" in out["lists"] and "secondary" in out["lists"]
    assert out["lists"]["prime"]["scanned_count"] >= 1
    panel = "\n".join(out["lists"]["prime"]["panels"])
    assert "COMMAND ROOM" in panel and "dma20" in panel.lower()
    assert "chips(" in panel.lower()
    assert out["lists"]["prime"]["prob_chips_last"]
