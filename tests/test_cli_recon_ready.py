import json

from optipanel.cli.main import recon_main


def test_recon_json_contains_readiness(tmp_path, capsys):
    feats = {
        "AAA": {
            "last": 105.0,
            "dma20": 100.0,
            "support": 101.0,
            "resistance": 106.0,
            "rvol": 1.6,
            "rs_strength": 0.30,
            "vwap_diff": 0.012,
        },
        "BBB": {
            "last": 95.0,
            "dma20": 100.0,
            "support": 96.0,
            "resistance": 100.0,
            "rvol": 1.5,
            "rs_strength": -0.25,
            "vwap_diff": -0.012,
        },
    }
    yml = tmp_path / "feats.yaml"
    yml.write_text(json.dumps(feats))

    code = recon_main(
        [
            "--symbols",
            "AAA,BBB",
            "--provider",
            "mock",
            "--features-yaml",
            str(yml),
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    for sym in ("AAA", "BBB"):
        readiness = out[sym].get("readiness")
        assert readiness is not None
        assert 0 <= readiness["attack"] <= 100
        assert 0 <= readiness["defense"] <= 100
        components = readiness.get("components")
        assert isinstance(components, dict)
        for key in ("attack_core", "defense_core", "sustainability", "fakeout_risk", "acceptance"):
            assert 0 <= components.get(key, 0) <= 100
