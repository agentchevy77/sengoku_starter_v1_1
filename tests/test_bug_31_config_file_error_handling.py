"""Unit tests for Bug #31: Unhandled Read Error on Configuration Files.

This test suite verifies that optipanel/ui/service.py properly handles various
I/O errors when reading configuration files, preventing application crashes.

Bug #31 Fix: The _read_text function now catches and wraps OSError subtypes
(PermissionError, FileNotFoundError, IsADirectoryError) with actionable
ConfigurationFileError messages.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from optipanel.ui.service import ConfigurationFileError, load_profiles


class TestBug31ConfigFileErrorHandling:
    """Test suite for Bug #31: Configuration file error handling."""

    def test_file_not_found_error_handling(self, tmp_path: Path) -> None:
        """Verify that missing configuration files raise ConfigurationFileError."""
        nonexistent = tmp_path / "does_not_exist.yaml"
        assert not nonexistent.exists()

        with pytest.raises(ConfigurationFileError) as exc_info:
            load_profiles(nonexistent)

        # Verify error message is actionable
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()
        assert str(nonexistent.resolve()) in error_msg
        assert "verify the file path" in error_msg.lower()

        # Verify exception chain is preserved for debugging
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, FileNotFoundError)

    def test_permission_error_handling(self, tmp_path: Path) -> None:
        """Verify that permission-denied errors raise ConfigurationFileError."""
        restricted_file = tmp_path / "restricted.yaml"
        restricted_file.write_text(
            """
watchlists:
  prime: [AAPL]
budgets:
  prime: {soft_cap: 10}
ui:
  width: 20
  top_n: 1
""",
            encoding="utf-8",
        )

        # Remove read permissions (owner=write-only, group=none, other=none)
        os.chmod(restricted_file, stat.S_IWUSR)

        try:
            with pytest.raises(ConfigurationFileError) as exc_info:
                load_profiles(restricted_file)

            # Verify error message is actionable
            error_msg = str(exc_info.value)
            assert "permission denied" in error_msg.lower()
            assert str(restricted_file.resolve()) in error_msg
            assert "read permissions" in error_msg.lower()

            # Verify exception chain is preserved for debugging
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, PermissionError)

        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_file, stat.S_IRUSR | stat.S_IWUSR)

    def test_is_directory_error_handling(self, tmp_path: Path) -> None:
        """Verify that directory-instead-of-file errors raise ConfigurationFileError."""
        directory_path = tmp_path / "config_dir"
        directory_path.mkdir()
        assert directory_path.is_dir()

        with pytest.raises(ConfigurationFileError) as exc_info:
            load_profiles(directory_path)

        # Verify error message is actionable
        error_msg = str(exc_info.value)
        assert "directory" in error_msg.lower()
        assert str(directory_path.resolve()) in error_msg
        assert "points to a configuration file" in error_msg.lower()

        # Verify exception chain is preserved for debugging
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, IsADirectoryError)

    def test_successful_file_read_still_works(self, tmp_path: Path) -> None:
        """Verify that valid configuration files are read successfully (regression test)."""
        valid_config = tmp_path / "valid.yaml"
        valid_config.write_text(
            """
watchlists:
  prime: [AAPL, TSLA]
  secondary: [MSFT]
budgets:
  prime: {soft_cap: 20, used_lines: 5}
  secondary: {soft_cap: 10, used_lines: 2}
ui:
  width: 30
  top_n: 3
""",
            encoding="utf-8",
        )

        # Should not raise any exception
        profiles = load_profiles(valid_config)

        # Verify data is parsed correctly
        assert profiles.prime == ["AAPL", "TSLA"]
        assert profiles.secondary == ["MSFT"]
        assert profiles.ui_width == 30
        assert profiles.top_n == 3
        assert "prime" in profiles.budgets
        assert profiles.budgets["prime"]["soft_cap"] == 20

    def test_error_message_includes_absolute_path(self, tmp_path: Path) -> None:
        """Verify that error messages always include absolute paths for clarity."""
        # Use a relative path input
        nonexistent = tmp_path / "subdir" / "config.yaml"

        with pytest.raises(ConfigurationFileError) as exc_info:
            load_profiles(nonexistent)

        error_msg = str(exc_info.value)
        # Error message should contain the absolute resolved path
        assert str(nonexistent.resolve()) in error_msg
        # Should not contain just the relative path
        assert error_msg.count(str(nonexistent.resolve())) >= 1

    def test_exception_chain_preserves_original_traceback(self, tmp_path: Path) -> None:
        """Verify that the exception chain preserves the original error for debugging."""
        nonexistent = tmp_path / "missing.yaml"

        with pytest.raises(ConfigurationFileError) as exc_info:
            load_profiles(nonexistent)

        # Verify the __cause__ attribute preserves the original exception
        original_error = exc_info.value.__cause__
        assert original_error is not None
        assert isinstance(original_error, FileNotFoundError)

        # Verify traceback information is preserved
        assert original_error.__traceback__ is not None

    def test_oserror_generic_handling(self, tmp_path: Path) -> None:
        """Verify that generic OSError is caught and wrapped appropriately.

        This test uses a mock to simulate rare I/O errors that aren't
        PermissionError, FileNotFoundError, or IsADirectoryError.
        """
        from unittest.mock import patch

        valid_config = tmp_path / "valid.yaml"
        valid_config.write_text(
            """
watchlists:
  prime: [AAPL]
budgets:
  prime: {soft_cap: 10}
ui:
  width: 20
  top_n: 1
""",
            encoding="utf-8",
        )

        # Mock read_text to raise a generic OSError
        with patch.object(Path, "read_text", side_effect=OSError("Disk read error")):
            with pytest.raises(ConfigurationFileError) as exc_info:
                load_profiles(valid_config)

            error_msg = str(exc_info.value)
            assert "failed to read" in error_msg.lower()
            assert "i/o error" in error_msg.lower()
            assert "disk read error" in error_msg.lower()

            # Verify exception chain
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, OSError)


def test_bug_31_integration_with_fetch_features(tmp_path: Path) -> None:
    """Integration test: Verify error handling in fetch_features (mock provider)."""
    from optipanel.ui.service import ProviderConfig, fetch_features

    nonexistent_features = tmp_path / "missing_features.yaml"

    with pytest.raises(ConfigurationFileError) as exc_info:
        fetch_features(
            ["AAPL", "TSLA"],
            provider=ProviderConfig(name="mock", features_path=nonexistent_features),
        )

    error_msg = str(exc_info.value)
    assert "not found" in error_msg.lower()
    assert str(nonexistent_features.resolve()) in error_msg


def test_bug_31_integration_with_run_tick(tmp_path: Path) -> None:
    """Integration test: Verify error handling in run_tick function."""
    from optipanel.ui.service import run_tick

    nonexistent_profiles = tmp_path / "missing_profiles.yaml"

    with pytest.raises(ConfigurationFileError) as exc_info:
        run_tick(nonexistent_profiles, "mock", features_yaml_path=None, width=20, top_n=1)

    error_msg = str(exc_info.value)
    assert "not found" in error_msg.lower()
    assert str(nonexistent_profiles.resolve()) in error_msg
