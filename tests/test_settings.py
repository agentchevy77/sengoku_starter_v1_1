import yaml

from optipanel import settings as settings_mod


def test_load_settings_defaults(tmp_path, monkeypatch):
    # Prepare a minimal defaults file in a temp config dir
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    defaults = {
        "market_data_budget": {
            "allowance_lines": 1000,
            "soft_cap_lines": 800,
            "rt_bars_max": 5,
            "snapshot_concurrency_max": 3,
            "backoff": {"cooldown_sec": 2},
        },
        "schedulers": {
            "prime_interval_sec": 1,
            "secondary_thin_interval_sec": 2,
        },
        "cache": {"max_items": 100, "default_ttl_sec": 60},
    }
    ypath = cfg_dir / "settings.defaults.yaml"
    ypath.write_text(yaml.safe_dump(defaults))

    # Point ROOT to the temp directory's parent to mimic project root
    monkeypatch.setattr(settings_mod, "ROOT", tmp_path)

    s = settings_mod.load_settings()
    assert s.allowance_lines == 1000
    assert s.backoff_cooldown_sec == 2
    assert s.cache_default_ttl_sec == 60
