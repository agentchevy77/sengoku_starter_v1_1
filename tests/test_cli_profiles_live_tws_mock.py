import json

import pytest

from optipanel.cli.main import profiles_live_cmd, profiles_live_main

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


def test_cli_profiles_live_tws_mock(tmp_path, capsys):
    prof_p = tmp_path / "profiles.yaml"
    feat_p = tmp_path / "features.yaml"
    prof_p.write_text(PROF_YAML)
    feat_p.write_text(FEAT_YAML)

    rc = profiles_live_main(
        ["--profiles-yaml", str(prof_p), "--provider", "tws-mock", "--features-yaml", str(feat_p), "--ticks", "3"]
    )
    assert rc == 0
    txt = capsys.readouterr().out
    data = json.loads(txt)
    assert "lists" in data and "prime" in data["lists"]
    assert data["lists"]["prime"]["provider_calls"] >= 1
    assert isinstance(data["lists"]["prime"]["panels"], list) and len(data["lists"]["prime"]["panels"]) >= 1


def test_profiles_live_cmd_requires_features_for_mock():
    with pytest.raises(ValueError) as excinfo:
        profiles_live_cmd(PROF_YAML, "mock", None)
    assert "features-yaml is required" in str(excinfo.value)


def test_profiles_live_cmd_requires_features_for_tws_mock():
    with pytest.raises(ValueError) as excinfo:
        profiles_live_cmd(PROF_YAML, "tws-mock", None)
    assert "features-yaml is required" in str(excinfo.value)


def test_profiles_live_cmd_tws_live_per_call(monkeypatch):
    captures = []

    class DummyFetcher:
        def __init__(self, cfg):
            captures.append(cfg)

        def features_for_symbols(self, symbols):
            return {
                s: {
                    "last": 0.0,
                    "dma20": 0.0,
                    "support": 0.0,
                    "resistance": 0.0,
                    "rvol": 1.0,
                    "rs_strength": 0.0,
                    "vwap_diff": 0.0,
                }
                for s in symbols
            }

    def fake_run_profiles(prof, provider, ticks):
        return {"ticks": ticks, "lists": {}}

    monkeypatch.setattr("optipanel.adapters.ibkr.RealTwsFetcher", DummyFetcher)
    monkeypatch.setattr("optipanel.adapters.ibkr.translator.translate_snapshots", lambda raw: raw)
    monkeypatch.setattr("optipanel.runtime.profiles_live.run_profiles_with_provider", fake_run_profiles)

    profiles_live_cmd(
        PROF_YAML,
        "tws-live",
        None,
        ticks=1,
        tws_host="1.2.3.4",
        tws_port=1234,
        tws_client_id=42,
        tws_ref_symbol="QQQ",
    )

    profiles_live_cmd(
        PROF_YAML,
        "tws-live",
        None,
        ticks=1,
        tws_host="5.6.7.8",
        tws_port=5678,
        tws_client_id=7,
        tws_ref_symbol="IWM",
    )

    assert [cfg.host for cfg in captures] == ["1.2.3.4", "5.6.7.8"]
    assert [cfg.port for cfg in captures] == [1234, 5678]
    assert [cfg.client_id for cfg in captures] == [42, 7]
    assert [cfg.ref_symbol for cfg in captures] == ["QQQ", "IWM"]
