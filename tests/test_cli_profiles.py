import json
from optipanel.cli.main import profiles_main

PROF_YAML = """
watchlists:
  prime: [AAA, BBB]
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

def test_cli_profiles_json(tmp_path, capsys):
    prof_p = tmp_path / "profiles.yaml"
    feat_p = tmp_path / "features.yaml"
    prof_p.write_text(PROF_YAML)
    feat_p.write_text(FEAT_YAML)
    rc = profiles_main(["--profiles-yaml", str(prof_p), "--features-yaml", str(feat_p), "--ticks", "3"])
    assert rc == 0
    txt = capsys.readouterr().out
    data = json.loads(txt)
    assert "lists" in data and "prime" in data["lists"] and "secondary" in data["lists"]
    assert isinstance(data["lists"]["prime"]["panels"], list) and len(data["lists"]["prime"]["panels"]) >= 1
