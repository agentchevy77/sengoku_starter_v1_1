"""Test for Bug #41: Insecure File Permissions on Secrets File

This test verifies that the SecretResolver properly checks and enforces
secure file permissions on secrets files to prevent unauthorized access.
"""

import json

import pytest

from optipanel.security import SecretResolver, SecretSource


class TestSecretFilePermissions:
    """Test suite for secure file permission checking in SecretResolver."""

    def test_secure_permissions_accepted(self, tmp_path):
        """Test that secure permissions (600) are accepted without warnings."""
        secrets = {"API_KEY": "secret123", "DATABASE_URL": "postgres://localhost"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set secure permissions (owner read/write only)
        secrets_file.chmod(0o600)

        # Should load without any issues
        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)
        assert resolver.get_str("API_KEY") == "secret123"

    def test_readonly_secure_permissions_accepted(self, tmp_path):
        """Test that read-only secure permissions (400) are accepted."""
        secrets = {"API_KEY": "secret456"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set secure read-only permissions
        secrets_file.chmod(0o400)

        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)
        assert resolver.get_str("API_KEY") == "secret456"

    def test_world_readable_permissions_rejected_strict(self, tmp_path):
        """Test that world-readable permissions are rejected in strict mode."""
        secrets = {"API_KEY": "exposed"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set world-readable permissions (INSECURE!)
        secrets_file.chmod(0o644)  # rw-r--r--

        # Should raise PermissionError in strict mode
        with pytest.raises(PermissionError, match="world-readable"):
            SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)

    def test_group_readable_permissions_rejected_strict(self, tmp_path):
        """Test that group-readable permissions are rejected in strict mode."""
        secrets = {"API_KEY": "group-exposed"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set group-readable permissions (INSECURE!)
        secrets_file.chmod(0o640)  # rw-r-----

        # Should raise PermissionError in strict mode
        with pytest.raises(PermissionError, match="group-readable"):
            SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)

    def test_world_readable_permissions_warned_non_strict(self, tmp_path, caplog):
        """Test that world-readable permissions generate warning in non-strict mode."""
        secrets = {"API_KEY": "warned"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set world-readable permissions
        secrets_file.chmod(0o644)

        # Should load but generate warning in non-strict mode
        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=False)

        # Verify it still loads
        assert resolver.get_str("API_KEY") == "warned"

        # Check for warning in logs
        assert any("world-readable" in record.message for record in caplog.records)

    def test_environment_variable_override(self, tmp_path, monkeypatch):
        """Test that SENGOKU_SECRETS_STRICT_PERMISSIONS env var controls strict mode."""
        secrets = {"API_KEY": "env-test"}
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps(secrets))

        # Set insecure permissions
        secrets_file.chmod(0o644)

        # Test with strict mode disabled via env var
        monkeypatch.setenv("SENGOKU_SECRETS_SOURCE", "file")
        monkeypatch.setenv("SENGOKU_SECRETS_FILE", str(secrets_file))
        monkeypatch.setenv("SENGOKU_SECRETS_STRICT_PERMISSIONS", "false")

        # Should load without error when strict mode is disabled
        resolver = SecretResolver.from_environment()
        assert resolver.get_str("API_KEY") == "env-test"

        # Test with strict mode enabled (default)
        monkeypatch.setenv("SENGOKU_SECRETS_STRICT_PERMISSIONS", "true")

        # Should fail with strict mode enabled
        with pytest.raises(PermissionError, match="world-readable"):
            SecretResolver.from_environment()

    def test_various_permission_modes(self, tmp_path):
        """Test handling of various permission modes."""
        test_cases = [
            (0o777, True, pytest.raises(PermissionError)),  # rwxrwxrwx - VERY INSECURE
            (0o666, True, pytest.raises(PermissionError)),  # rw-rw-rw- - INSECURE
            (0o644, True, pytest.raises(PermissionError)),  # rw-r--r-- - world-readable
            (0o640, True, pytest.raises(PermissionError)),  # rw-r----- - group-readable
            (0o600, True, None),  # rw------- - SECURE
            (0o400, True, None),  # r-------- - SECURE (read-only)
            (0o700, True, None),  # rwx------ - OK (executable bit doesn't matter for owner)
        ]

        for mode, strict, expected_context in test_cases:
            secrets_file = tmp_path / f"secrets_{mode:o}.json"
            secrets_file.write_text(json.dumps({"KEY": f"value_{mode:o}"}))
            secrets_file.chmod(mode)

            if expected_context:
                with expected_context:
                    SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=strict)
            else:
                # Should succeed
                resolver = SecretResolver(
                    source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=strict
                )
                assert resolver.get_str("KEY") == f"value_{mode:o}"

    def test_permission_check_with_yaml_file(self, tmp_path):
        """Test that permission checking works with YAML files too."""
        pytest.importorskip("yaml")  # Skip if yaml not installed

        secrets_yaml = """
API_KEY: yaml-secret
DATABASE_URL: postgres://localhost
"""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text(secrets_yaml)

        # Set insecure permissions
        secrets_file.chmod(0o644)

        # Should fail in strict mode
        with pytest.raises(PermissionError, match="world-readable"):
            SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)

        # Fix permissions and verify it works
        secrets_file.chmod(0o600)
        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)
        assert resolver.get_str("API_KEY") == "yaml-secret"

    def test_nonexistent_file_still_fails(self, tmp_path):
        """Ensure that nonexistent files still raise FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError, match="Secrets file not found"):
            SecretResolver(source=SecretSource.FILE, file_path=str(nonexistent), strict_permissions=True)

    def test_empty_file_with_permissions(self, tmp_path, caplog):
        """Test that empty files are handled correctly with permission checks."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        # Even with insecure permissions, empty files should just warn about being empty
        empty_file.chmod(0o644)

        # In strict mode, should fail on permissions before checking content
        with pytest.raises(PermissionError, match="world-readable"):
            SecretResolver(source=SecretSource.FILE, file_path=str(empty_file), strict_permissions=True)

        # In non-strict mode, should warn about permissions AND empty file
        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(empty_file), strict_permissions=False)

        # Check for both warnings
        assert any("world-readable" in record.message for record in caplog.records)
        assert any("empty" in record.message for record in caplog.records)
