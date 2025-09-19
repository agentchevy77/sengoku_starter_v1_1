from optipanel.settings import Settings, load_settings


def test_load_settings_returns_defaults():
    settings = load_settings()

    assert isinstance(settings, Settings)
    assert settings.allowance_lines == 100
    assert settings.soft_cap_lines == 60
    assert settings.rt_bars_max == 3
    assert settings.snapshot_concurrency_max == 10
    assert settings.backoff_cooldown_sec == 60
    assert settings.prime_interval_sec == 5
    assert settings.secondary_thin_interval_sec == 10
    assert settings.cache_max_items == 512
    assert settings.cache_default_ttl_sec == 180
