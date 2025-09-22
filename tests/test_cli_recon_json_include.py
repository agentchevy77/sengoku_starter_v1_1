from __future__ import annotations

import json
from pathlib import Path

from optipanel.cli.main import recon_main

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}


def _write_yaml(tmp_path: Path, data: dict) -> str:
    path = tmp_path / "feats.yaml"
    import yaml

    path.write_text(yaml.safe_dump(data))
    return str(path)


def test_recon_json_baseline(tmp_path, capsys):
    feats_path = _write_yaml(tmp_path, {"AAA": BULL})
    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
        ]
    )
    out = json.loads(capsys.readouterr().out)
    entry = out["AAA"]
    assert "supply" not in entry
    assert "chips_summary" not in entry
    sustain = entry.get("sustainment")
    assert sustain and "sustainability" in sustain and "fakeout_risk" in sustain
    readiness = entry.get("readiness")
    assert readiness and readiness["attack"] >= 0 and readiness["defense"] >= 0


def test_recon_json_include_supply(tmp_path, capsys):
    feats_path = _write_yaml(tmp_path, {"AAA": BULL})
    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
            "--include-supply",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    entry = out["AAA"]
    assert "supply" in entry and entry["supply"]
    sustain = entry.get("sustainment")
    assert sustain and "sustainability" in sustain and "fakeout_risk" in sustain
    assert entry.get("readiness", {}).get("attack") is not None


def test_recon_json_include_summary(tmp_path, capsys):
    feats_path = _write_yaml(tmp_path, {"AAA": BULL})
    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
            "--json-include",
            "chips_summary",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    entry = out["AAA"]
    summary = entry.get("chips_summary")
    assert summary and "D" in summary
    sustain = entry.get("sustainment")
    assert sustain
    assert "readiness" in entry


def test_recon_micro_mode_returns_scout_block(tmp_path, capsys):
    feats_path = _write_yaml(tmp_path, {"AAA": BULL})
    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
            "--mode",
            "micro",
        ]
    )
    entry_micro = json.loads(capsys.readouterr().out)["AAA"]

    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
        ]
    )
    entry_prob = json.loads(capsys.readouterr().out)["AAA"]

    assert entry_micro["recon"] == entry_prob["recon"]
    assert entry_micro["sustainment"] == entry_prob["sustainment"]
    assert "timeframes" in entry_micro and "timeframes" in entry_prob
    assert entry_micro.get("tf_scout")


def test_recon_pretty_includes_supply_and_acceptance(tmp_path, capsys):
    features = {
        "AAA": {
            "last": 105.0,
            "dma20": 100.0,
            "support": 101.0,
            "resistance": 106.0,
            "rvol": 1.6,
            "rs_strength": 0.30,
            "vwap_diff": 0.012,
            "bars": [
                {"open": 100.5, "high": 101.1, "low": 100.2, "close": 100.9, "volume": 900},
                {"open": 101.0, "high": 106.6, "low": 101.0, "close": 106.3, "volume": 1500},
                {"open": 106.1, "high": 106.8, "low": 105.7, "close": 106.4, "volume": 1100},
            ],
        }
    }
    feats_path = _write_yaml(tmp_path, features)

    recon_main(
        [
            "--symbols",
            "AAA",
            "--provider",
            "mock",
            "--features-yaml",
            feats_path,
            "--pretty",
            "--include-supply",
        ]
    )
    out = capsys.readouterr().out
    lower = out.lower()
    assert "=== recon aaa" in lower
    assert "scout     recon" in lower
    assert "sustain" in lower and "fakeout" in lower
    assert "readiness" in lower and "attack=" in lower
    assert "scout    m15" in lower
    assert "supply" in lower and "⇐" in out
    assert "accept" in lower
