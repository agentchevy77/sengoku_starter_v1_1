from pathlib import Path

from optipanel.config.loader import load_profiles_yaml
from optipanel.runtime.profiles import run_profiles_offline

FIXTURES = Path(__file__).parents[1] / "config" / "examples"


def test_run_profiles_offline_produces_panels(example_profiles, example_features):
    out = run_profiles_offline(example_profiles, example_features, ticks=3)
    assert "lists" in out and "prime" in out["lists"] and "secondary" in out["lists"]
    assert out["lists"]["prime"]["scanned_count"] >= 1
    panel = "\n".join(out["lists"]["prime"]["panels"])
    assert "COMMAND ROOM" in panel and "dma20" in panel.lower()
    assert "chips(" in panel.lower()
    assert out["lists"]["prime"]["prob_chips_last"]


def test_load_profiles_yaml(tmp_path, example_profiles_yaml):
    path = tmp_path / "profiles.yaml"
    path.write_text(example_profiles_yaml, encoding="utf-8")
    prof = load_profiles_yaml(path)
    assert prof["watchlists"]["prime"] == ["AAA", "BBB"]
