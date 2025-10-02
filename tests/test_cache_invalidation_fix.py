"""Test suite for Issue #5: Critical Cache Invalidation Fix

This test verifies that the cache properly invalidates when configuration
files are modified, ensuring users see updated data without restarting the API.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from optipanel.api.app import _tick_cache, gather_panels


class TestCacheInvalidationFix:
    """Test suite for cache invalidation based on file modification times."""

    @pytest.fixture
    def temp_config_files(self):
        """Create temporary config files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_path = Path(temp_dir) / "profiles.yaml"
            features_path = Path(temp_dir) / "features.yaml"

            # Create initial config files
            profiles_path.write_text(
                """
ui:
  width: 80
  top_n: 10
watchlists:
  main:
    - AAPL
    - MSFT
"""
            )
            features_path.write_text(
                """
features:
  - name: test_feature
    enabled: true
"""
            )

            yield profiles_path, features_path

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the cache before and after each test."""
        _tick_cache._data.clear()
        yield
        _tick_cache._data.clear()

    def test_cache_invalidates_on_profiles_change(self, temp_config_files):
        """Test that cache invalidates when profiles.yaml is modified."""
        profiles_path, features_path = temp_config_files

        # Mock the expensive operations
        with (
            patch("optipanel.api.app.load_profiles") as mock_load_profiles,
            patch("optipanel.api.app.run_tick") as mock_run_tick,
        ):

            # Setup mocks
            mock_profile = MagicMock()
            mock_profile.ui_width = 80
            mock_profile.top_n = 10
            mock_load_profiles.return_value = mock_profile

            mock_run_tick.return_value = {
                "run": {
                    "lists": {
                        "main": {
                            "features": {
                                "AAPL": {"last": 150.0, "volume": 1000000},
                                "MSFT": {"last": 300.0, "volume": 2000000},
                            }
                        }
                    }
                }
            }

            # First call - should cache the result
            panels1, meta1 = gather_panels(
                provider_name="test",
                profiles_path=profiles_path,
                features_path=features_path,
                cache_ttl=300.0,  # 5 minute TTL
            )

            # Verify cache was populated
            assert len(_tick_cache._data) == 1
            first_call_count = mock_run_tick.call_count

            # Second call with same files - should use cache
            panels2, meta2 = gather_panels(
                provider_name="test", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Should not have called run_tick again
            assert mock_run_tick.call_count == first_call_count

            # Now modify the profiles file
            time.sleep(0.01)  # Ensure different mtime (some filesystems have coarse granularity)
            profiles_path.write_text(
                """
ui:
  width: 100
  top_n: 20
watchlists:
  main:
    - AAPL
    - MSFT
    - GOOGL
"""
            )

            # Third call after file modification - should invalidate cache
            mock_run_tick.return_value = {
                "run": {
                    "lists": {
                        "main": {
                            "features": {
                                "AAPL": {"last": 155.0, "volume": 1100000},
                                "MSFT": {"last": 305.0, "volume": 2100000},
                                "GOOGL": {"last": 2000.0, "volume": 3000000},
                            }
                        }
                    }
                }
            }

            panels3, meta3 = gather_panels(
                provider_name="test", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Should have called run_tick again due to cache invalidation
            assert mock_run_tick.call_count == first_call_count + 1

            # Cache should now have 2 entries (old one expired, new one created)
            assert len(_tick_cache._data) >= 1

    def test_cache_invalidates_on_features_change(self, temp_config_files):
        """Test that cache invalidates when features.yaml is modified."""
        profiles_path, features_path = temp_config_files

        with (
            patch("optipanel.api.app.load_profiles") as mock_load_profiles,
            patch("optipanel.api.app.run_tick") as mock_run_tick,
        ):

            # Setup mocks
            mock_profile = MagicMock()
            mock_profile.ui_width = 80
            mock_profile.top_n = 10
            mock_load_profiles.return_value = mock_profile

            mock_run_tick.return_value = {"run": {"lists": {}}}

            # First call
            gather_panels(
                provider_name="test", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            first_call_count = mock_run_tick.call_count

            # Modify features file
            time.sleep(0.01)
            features_path.write_text(
                """
features:
  - name: test_feature
    enabled: false
  - name: new_feature
    enabled: true
"""
            )

            # Second call after modification
            gather_panels(
                provider_name="test", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Should have called run_tick again
            assert mock_run_tick.call_count == first_call_count + 1

    def test_cache_handles_missing_files_gracefully(self):
        """Test that cache handles missing config files without crashing."""
        non_existent_profiles = Path("/non/existent/profiles.yaml")
        non_existent_features = Path("/non/existent/features.yaml")

        with (
            patch("optipanel.api.app.load_profiles") as mock_load_profiles,
            patch("optipanel.api.app.run_tick") as mock_run_tick,
        ):

            mock_profile = MagicMock()
            mock_profile.ui_width = 80
            mock_profile.top_n = 10
            mock_load_profiles.return_value = mock_profile
            mock_run_tick.return_value = {"run": {"lists": {}}}

            # Should not crash even with non-existent files
            panels, meta = gather_panels(
                provider_name="test",
                profiles_path=non_existent_profiles,
                features_path=non_existent_features,
                cache_ttl=300.0,
            )

            # Should have created a cache entry with None mtimes
            assert len(_tick_cache._data) == 1
            cache_key = next(iter(_tick_cache._data.keys()))
            assert cache_key[1] is None  # profiles_mtime
            assert cache_key[4] is None  # features_mtime

    def test_cache_key_includes_all_relevant_fields(self, temp_config_files):
        """Test that cache key includes all necessary fields for proper invalidation."""
        profiles_path, features_path = temp_config_files

        with (
            patch("optipanel.api.app.load_profiles") as mock_load_profiles,
            patch("optipanel.api.app.run_tick") as mock_run_tick,
        ):

            mock_profile = MagicMock()
            mock_profile.ui_width = 80
            mock_profile.top_n = 10
            mock_load_profiles.return_value = mock_profile
            mock_run_tick.return_value = {"run": {"lists": {}}}

            # Make a call to populate cache
            gather_panels(
                provider_name="test_provider", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Examine the cache key structure
            assert len(_tick_cache._data) == 1
            cache_key = next(iter(_tick_cache._data.keys()))

            # Verify key structure (7 elements)
            assert len(cache_key) == 7
            assert str(profiles_path) in cache_key[0]  # profiles path
            assert cache_key[1] is not None  # profiles mtime (file exists)
            assert cache_key[2] == "test_provider"  # provider name
            assert str(features_path) in cache_key[3]  # features path
            assert cache_key[4] is not None  # features mtime (file exists)
            assert cache_key[5] == 80  # ui_width
            assert cache_key[6] == 10  # top_n

    def test_different_providers_use_different_cache_entries(self, temp_config_files):
        """Test that different providers maintain separate cache entries."""
        profiles_path, features_path = temp_config_files

        with (
            patch("optipanel.api.app.load_profiles") as mock_load_profiles,
            patch("optipanel.api.app.run_tick") as mock_run_tick,
        ):

            mock_profile = MagicMock()
            mock_profile.ui_width = 80
            mock_profile.top_n = 10
            mock_load_profiles.return_value = mock_profile
            mock_run_tick.return_value = {"run": {"lists": {}}}

            # Call with provider1
            gather_panels(
                provider_name="provider1", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Call with provider2
            gather_panels(
                provider_name="provider2", profiles_path=profiles_path, features_path=features_path, cache_ttl=300.0
            )

            # Should have two separate cache entries
            assert len(_tick_cache._data) == 2

            # Verify both providers are in cache keys
            cache_keys = list(_tick_cache._data.keys())
            providers = [key[2] for key in cache_keys]
            assert "provider1" in providers
            assert "provider2" in providers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
