"""Comprehensive regression coverage for Bug #57: tick cache configuration.

This suite exercises the new ``TickCacheSettings`` surface while ensuring the legacy
``CacheConfig`` shim stays functional until all regressions migrate. The tests validate:

1. Default values and validation semantics on the modern settings object
2. Environment-variable resolution via ``ConfigResolver`` (parity with historical shim)
3. Integration of the settings with ``_TickCache`` (prune cadence, cooldowns, timeouts)
4. Backward compatibility when the deprecated ``CacheConfig`` is used
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import patch

import pytest

from optipanel.api.app import CacheConfig, TickCacheSettings, _TickCache
from optipanel.cli.config import ConfigResolver


class TestTickCacheSettingsDefaults:
    """Validate default construction mirrors the historical constants."""

    def test_defaults_match_legacy_contract(self) -> None:
        settings = TickCacheSettings()
        assert settings.prune_interval == pytest.approx(60.0)
        assert settings.failure_cooldown == pytest.approx(5.0)
        assert settings.wait_timeout == pytest.approx(30.0)

    def test_custom_initialisation(self) -> None:
        settings = TickCacheSettings(prune_interval=90, failure_cooldown=7.5, wait_timeout=42)
        assert settings.prune_interval == pytest.approx(90.0)
        assert settings.failure_cooldown == pytest.approx(7.5)
        assert settings.wait_timeout == pytest.approx(42.0)


class TestTickCacheSettingsValidation:
    """Ensure guard rails are preserved on the modern settings surface."""

    def test_negative_prune_interval_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="prune_interval must be >= 0"):
            TickCacheSettings(prune_interval=-0.1)

    def test_negative_failure_cooldown_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="failure_cooldown must be >= 0"):
            TickCacheSettings(failure_cooldown=-1)

    def test_negative_wait_timeout_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="wait_timeout must be >= 0"):
            TickCacheSettings(wait_timeout=-5)

    def test_zero_values_are_allowed(self) -> None:
        settings = TickCacheSettings(prune_interval=0, failure_cooldown=0, wait_timeout=0)
        assert settings.prune_interval == pytest.approx(0.0)
        assert settings.failure_cooldown == pytest.approx(0.0)
        assert settings.wait_timeout == pytest.approx(0.0)

    def test_low_prune_interval_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        TickCacheSettings(prune_interval=0.5)
        assert any("TickCacheSettings: prune_interval=0.5s is very low" in record.message for record in caplog.records)

    def test_high_wait_timeout_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        TickCacheSettings(wait_timeout=600.0)
        assert any("TickCacheSettings: wait_timeout=600.0s is very high" in record.message for record in caplog.records)


class TestTickCacheSettingsFromEnv:
    """Confirm environment resolution matches the historical behaviour."""

    def test_defaults_are_used_when_env_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = TickCacheSettings.from_env()
        assert settings.prune_interval == pytest.approx(60.0)
        assert settings.failure_cooldown == pytest.approx(5.0)
        assert settings.wait_timeout == pytest.approx(30.0)

    def test_each_env_var_overrides_individually(self) -> None:
        with patch.dict(os.environ, {"SENGOKU_CACHE_PRUNE_INTERVAL": "120.0"}):
            settings = TickCacheSettings.from_env()
        assert settings.prune_interval == pytest.approx(120.0)
        assert settings.failure_cooldown == pytest.approx(5.0)

        with patch.dict(os.environ, {"SENGOKU_CACHE_FAILURE_COOLDOWN": "12.5"}):
            settings = TickCacheSettings.from_env()
        assert settings.failure_cooldown == pytest.approx(12.5)

        with patch.dict(os.environ, {"SENGOKU_CACHE_WAIT_TIMEOUT": "75"}):
            settings = TickCacheSettings.from_env()
        assert settings.wait_timeout == pytest.approx(75.0)

    def test_all_env_vars_override_simultaneously(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SENGOKU_CACHE_PRUNE_INTERVAL": "180",
                "SENGOKU_CACHE_FAILURE_COOLDOWN": "15",
                "SENGOKU_CACHE_WAIT_TIMEOUT": "90",
            },
        ):
            settings = TickCacheSettings.from_env()

        assert settings.prune_interval == pytest.approx(180.0)
        assert settings.failure_cooldown == pytest.approx(15.0)
        assert settings.wait_timeout == pytest.approx(90.0)

    def test_invalid_env_value_falls_back_to_default(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch.dict(os.environ, {"SENGOKU_CACHE_PRUNE_INTERVAL": "not-a-number"}):
            settings = TickCacheSettings.from_env()

        assert settings.prune_interval == pytest.approx(60.0)
        assert any("Invalid float" in record.message for record in caplog.records)

    def test_custom_resolver_is_supported(self) -> None:
        resolver = ConfigResolver()
        with patch.dict(os.environ, {"SENGOKU_CACHE_PRUNE_INTERVAL": "240"}):
            settings = TickCacheSettings.from_env(resolver=resolver)
        assert settings.prune_interval == pytest.approx(240.0)


class TestTickCacheIntegration:
    """Validate _TickCache wiring against the new settings surface."""

    def test_tick_cache_accepts_settings(self) -> None:
        settings = TickCacheSettings(prune_interval=100, failure_cooldown=8, wait_timeout=45)
        cache = _TickCache(settings=settings)
        assert cache._config is settings
        assert cache._prune_interval == pytest.approx(100.0)
        assert cache._failure_cooldown_sec == pytest.approx(8.0)
        assert cache._wait_timeout == pytest.approx(45.0)

    def test_tick_cache_defaults_to_env_settings(self) -> None:
        with patch.dict(os.environ, {"SENGOKU_CACHE_PRUNE_INTERVAL": "150.0"}):
            cache = _TickCache()
        assert cache._prune_interval == pytest.approx(150.0)

    def test_prune_interval_controls_pruning_cadence(self) -> None:
        settings = TickCacheSettings(prune_interval=0.1)
        cache = _TickCache(settings=settings)
        cache.get_or_create(("demo",), ttl=1.0, loader=lambda: {"data": 1})
        first_prune = cache._last_prune
        assert first_prune > 0

        time.sleep(0.05)
        cache.get_or_create(("demo",), ttl=1.0, loader=lambda: {"data": 1})
        assert cache._last_prune == first_prune

        time.sleep(0.1)
        cache.get_or_create(("demo",), ttl=1.0, loader=lambda: {"data": 1})
        assert cache._last_prune > first_prune

    def test_failure_cooldown_controls_retry_window(self) -> None:
        settings = TickCacheSettings(failure_cooldown=2.0)
        cache = _TickCache(settings=settings)

        def failing_loader() -> dict[str, str]:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            cache.get_or_create(("key",), ttl=10.0, loader=failing_loader)

        now = time.time()
        cooldown_until = cache._failure_cooldowns.get(("key",))
        assert cooldown_until is not None
        assert 1.8 <= (cooldown_until - now) <= 2.2

    def test_wait_timeout_controls_inflight_backoff(self) -> None:
        settings = TickCacheSettings(wait_timeout=1.0)
        cache = _TickCache(settings=settings)

        loader_started = threading.Event()
        loader_release = threading.Event()

        def slow_loader() -> dict[str, str]:
            loader_started.set()
            loader_release.wait(timeout=5.0)
            return {"ok": True}

        def blocking_thread() -> None:
            cache.get_or_create(("slow",), ttl=5.0, loader=slow_loader)

        t1 = threading.Thread(target=blocking_thread, daemon=True)
        t1.start()
        loader_started.wait(timeout=2.0)
        time.sleep(0.1)

        start = time.time()
        t2 = threading.Thread(target=blocking_thread, daemon=True)
        t2.start()
        time.sleep(1.4)
        elapsed = time.time() - start

        assert 1.0 <= elapsed <= 2.2

        loader_release.set()
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)


class TestLegacyCacheConfigCompatibility:
    """Keep the shim honest until downstream suites migrate."""

    def test_cache_config_from_env_still_works(self) -> None:
        with patch.dict(os.environ, {"SENGOKU_CACHE_WAIT_TIMEOUT": "75"}):
            config = CacheConfig.from_env()
        assert config.wait_timeout == pytest.approx(75.0)

    def test_tick_cache_accepts_cache_config_with_warning(self) -> None:
        config = CacheConfig(prune_interval=90.0, failure_cooldown=6.0, wait_timeout=33.0)
        with pytest.warns(DeprecationWarning):
            cache = _TickCache(config=config)
        assert cache._prune_interval == pytest.approx(90.0)
        assert cache._failure_cooldown_sec == pytest.approx(6.0)
        assert cache._wait_timeout == pytest.approx(33.0)


class TestDocumentationParity:
    """Docstrings should guide operators to the correct APIs."""

    def test_tick_cache_settings_docstring_mentions_legacy(self) -> None:
        doc = TickCacheSettings.__doc__
        assert doc is not None
        assert "CacheConfig" in doc

    def test_cache_config_docstring_retained_for_legacy_consumers(self) -> None:
        doc = CacheConfig.__doc__
        assert doc is not None
        assert "Legacy cache tuning options" in doc
