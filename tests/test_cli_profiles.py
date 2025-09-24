import json
from pathlib import Path

from optipanel.cli.main import profiles_main

FIXTURES = Path(__file__).parents[1] / "config" / "examples"


def test_cli_profiles_json(tmp_path, capsys):
    prof_p = tmp_path / "profiles.yaml"
    feat_p = tmp_path / "features.yaml"
    prof_p.write_text((FIXTURES / "profiles.yaml").read_text())
    feat_p.write_text((FIXTURES / "features.yaml").read_text())
    rc = profiles_main(["--profiles-yaml", str(prof_p), "--features-yaml", str(feat_p), "--ticks", "3"])
    assert rc == 0
    txt = capsys.readouterr().out
    data = json.loads(txt)
    assert "lists" in data and "prime" in data["lists"] and "secondary" in data["lists"]
    assert isinstance(data["lists"]["prime"]["panels"], list) and len(data["lists"]["prime"]["panels"]) >= 1
