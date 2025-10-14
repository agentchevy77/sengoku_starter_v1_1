from __future__ import annotations

from pathlib import Path

from optipanel.ui.service import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_PROFILES_PATH,
    ProviderConfig,
    budget_status,
    combine_watchlists,
    compute_panel,
    fetch_features,
    load_profiles,
    run_tick,
)


def test_load_profiles_defaults() -> None:
    profiles = load_profiles(DEFAULT_PROFILES_PATH)
    assert profiles.prime  # prime watchlist populated
    assert profiles.ui_width > 0
    ordered = combine_watchlists(profiles)
    # ensure ordering preserves prime first
    assert ordered[: len(profiles.prime)] == profiles.prime


def test_fetch_features_mock_roundtrip() -> None:
    feats = fetch_features(["aaa", "bbb"], provider=ProviderConfig(name="mock", features_path=DEFAULT_FEATURES_PATH))
    assert set(feats.keys()) == {"AAA", "BBB"}
    assert all("last" in f for f in feats.values())


def test_compute_panel_basic() -> None:
    feats = fetch_features(["AAA"], provider=ProviderConfig(name="mock", features_path=DEFAULT_FEATURES_PATH))
    panel = compute_panel("AAA", feats["AAA"], battlefield_width=20)
    assert panel.symbol == "AAA"
    assert 0 <= panel.recon_score <= 100
    assert "TOTAL" in panel.battlefield
    assert panel.readiness  # readiness block populated


def test_budget_status_states() -> None:
    ok = budget_status("prime", {"used_lines": 5, "soft_cap": 20})
    assert ok.status == "ok" and ok.emoji == "🟢"

    cooling = budget_status("prime", {"used_lines": 5, "soft_cap": 20, "cooldown": 1})
    assert cooling.status == "cooling" and cooling.emoji == "🟡"

    backoff = budget_status("prime", {"used_lines": 25, "soft_cap": 20})
    assert backoff.status == "backoff" and backoff.emoji == "🔴"


def test_run_tick_mock(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.yaml"
    features = tmp_path / "features.yaml"
    profiles.write_text(
        """
watchlists:
  prime: [AAA]
budgets:
  prime: {soft_cap: 10, used_lines: 0}
ui:
  width: 20
  top_n: 1
""",
        encoding="utf-8",
    )
    features.write_text(
        """
AAA:
  last: 105
  dma20: 100
  support: 102
  resistance: 110
  rvol: 1.4
  rs_strength: 0.2
  vwap_diff: 0.01
""",
        encoding="utf-8",
    )

    out = run_tick(profiles, "mock", features_yaml_path=features, width=20, top_n=1)
    assert out["run"]["ticks"] == 1
    assert out["run"]["lists"]["prime"]["provider_calls"] == 1
    assert isinstance(out["panel"], str) and out["panel"]
