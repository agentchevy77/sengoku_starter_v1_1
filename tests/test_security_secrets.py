import json

import pytest

from optipanel.security import SecretResolver, SecretSource, resolve_secret


def test_secret_resolver_environment(monkeypatch):
    monkeypatch.setenv("SENGOKU_SECRETS_SOURCE", "env")
    monkeypatch.setenv("TOP_SECRET", "alpha")

    resolver = SecretResolver.from_environment()
    assert resolver.get_str("TOP_SECRET") == "alpha"

    with pytest.raises(KeyError):
        resolver.resolve("MISSING", required=True)


def test_secret_resolver_file_source(tmp_path, monkeypatch):
    secrets = {"SENGOKU_TWS_HOST": "10.0.0.5", "SENGOKU_TWS_PORT": 5000, "FLAG": "1"}
    secrets_path = tmp_path / "secrets.json"
    secrets_path.write_text(json.dumps(secrets))

    # Set secure permissions on the secrets file (Bug #41 fix)
    secrets_path.chmod(0o600)

    monkeypatch.setenv("SENGOKU_SECRETS_SOURCE", "file")
    monkeypatch.setenv("SENGOKU_SECRETS_FILE", str(secrets_path))
    monkeypatch.setenv("SENGOKU_TWS_HOST", "should_not_leak")

    resolver = SecretResolver.from_environment()
    assert resolver.get_str("SENGOKU_TWS_HOST") == "10.0.0.5"
    assert resolver.get_int("SENGOKU_TWS_PORT") == 5000
    assert resolver.get_bool("FLAG") is True


def test_resolve_secret_helper(monkeypatch):
    monkeypatch.setenv("SENGOKU_SECRETS_SOURCE", "env")
    monkeypatch.setenv("SENGOKU_MAGIC", "open-sesame")

    assert resolve_secret("SENGOKU_MAGIC") == "open-sesame"


def test_secret_source_defaults_to_env(monkeypatch):
    monkeypatch.delenv("SENGOKU_SECRETS_SOURCE", raising=False)
    resolver = SecretResolver.from_environment()
    assert resolver.source == SecretSource.ENV
