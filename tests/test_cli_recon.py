import json

import pytest

from optipanel.cli.main import recon_main


@pytest.mark.parametrize("provider", ["tws-live"])
def test_recon_main_requires_symbols(provider, monkeypatch):
    if provider == "tws-live":

        class DummyFetcher:
            def __init__(self, cfg):
                pass

            def features_for_symbols(self, symbols):
                return {sym: {} for sym in symbols}

        monkeypatch.setenv("SENGOKU_TWS_HOST", "127.0.0.1")
        monkeypatch.setenv("SENGOKU_TWS_PORT", "7497")
        monkeypatch.setenv("SENGOKU_TWS_CLIENT_ID", "107")
        monkeypatch.setenv("SENGOKU_TWS_REF", "SPY")
        monkeypatch.setitem(
            recon_main.__globals__,
            "RealTwsFetcher",
            DummyFetcher,
        )

    with pytest.raises(SystemExit):
        recon_main(["--symbols", "", "--provider", provider])


def test_recon_main_mock(tmp_path):
    features_yaml = tmp_path / "features.yaml"
    features_yaml.write_text(
        """
AAA:
  last: 105.0
  dma20: 100.0
  support: 101.0
  resistance: 106.0
  rvol: 1.6
  rs_strength: 0.3
  vwap_diff: 0.012
BBB:
  last: 95.0
  dma20: 100.0
  support: 96.0
  resistance: 100.0
  rvol: 1.1
  rs_strength: -0.2
  vwap_diff: -0.01
"""
    )

    result = recon_main(
        [
            "--symbols",
            "AAA,BBB",
            "--provider",
            "mock",
            "--features-yaml",
            str(features_yaml),
        ]
    )
    assert result == 0


@pytest.mark.parametrize("provider", ["mock"])
def test_recon_main_output(monkeypatch, tmp_path, provider, capsys):
    features_yaml = tmp_path / "features.yaml"
    features_yaml.write_text(
        """
AAA:
  last: 105.0
  dma20: 100.0
  support: 101.0
  resistance: 106.0
  rvol: 1.6
  rs_strength: 0.3
  vwap_diff: 0.012
"""
    )
    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            provider,
            "--features-yaml",
            str(features_yaml),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert "AAA" in out
    assert "recon" in out["AAA"]
    assert "aggregate" in out["AAA"]
    assert "timeframes" in out["AAA"]
