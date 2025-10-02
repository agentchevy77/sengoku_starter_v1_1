"""Tests for unified CLI configuration and validation layer.

Tests Bugs #11 and #12 fixes:
- Bug #11: Centralized configuration with consistent precedence
- Bug #12: Defensive data mutation patterns
"""

import pytest

from optipanel.cli.config import ConfigResolver, InputValidator, ValidationError, safe_copy_alerts


class TestConfigResolver:
    """Test centralized configuration resolution with clear precedence."""

    def test_get_str_cli_precedence(self):
        """CLI value takes precedence over env var and default."""
        resolver = ConfigResolver()
        result = resolver.get_str("host", cli_value="192.168.1.1", env_key="HOST", default="127.0.0.1")
        assert result == "192.168.1.1"

    def test_get_str_env_fallback(self, monkeypatch):
        """Env var used when CLI value is None."""
        monkeypatch.setenv("HOST", "10.0.0.1")
        resolver = ConfigResolver()
        result = resolver.get_str("host", cli_value=None, env_key="HOST", default="127.0.0.1")
        assert result == "10.0.0.1"

    def test_get_str_default_fallback(self):
        """Default used when both CLI and env are None."""
        resolver = ConfigResolver()
        result = resolver.get_str("host", cli_value=None, env_key="MISSING", default="127.0.0.1")
        assert result == "127.0.0.1"

    def test_get_int_cli_precedence(self):
        """CLI integer takes precedence."""
        resolver = ConfigResolver()
        result = resolver.get_int("port", cli_value=8080, env_key="PORT", default=7496)
        assert result == 8080

    def test_get_int_env_conversion(self, monkeypatch):
        """Env var string converted to int."""
        monkeypatch.setenv("PORT", "9000")
        resolver = ConfigResolver()
        result = resolver.get_int("port", cli_value=None, env_key="PORT", default=7496)
        assert result == 9000

    def test_get_int_env_invalid_fallback_to_default(self, monkeypatch, caplog):
        """Invalid env var falls back to default with warning."""
        monkeypatch.setenv("PORT", "not_a_number")
        resolver = ConfigResolver()
        result = resolver.get_int("port", cli_value=None, env_key="PORT", default=7496)
        assert result == 7496
        assert "Invalid integer" in caplog.text
        assert "PORT" in caplog.text

    def test_get_float_cli_precedence(self):
        """CLI float takes precedence."""
        resolver = ConfigResolver()
        result = resolver.get_float("ttl", cli_value=3.14, env_key="TTL", default=1.0)
        assert result == 3.14

    def test_get_float_env_conversion(self, monkeypatch):
        """Env var string converted to float."""
        monkeypatch.setenv("TTL", "2.5")
        resolver = ConfigResolver()
        result = resolver.get_float("ttl", cli_value=None, env_key="TTL", default=1.0)
        assert result == 2.5

    def test_get_bool_cli_precedence(self):
        """CLI bool takes precedence."""
        resolver = ConfigResolver()
        result = resolver.get_bool("verbose", cli_value=True, env_key="VERBOSE", default=False)
        assert result is True

    def test_get_bool_env_truthy_values(self, monkeypatch):
        """Env var parsed as boolean with lenient matching."""
        resolver = ConfigResolver()
        for truthy in ["1", "true", "TRUE", "yes", "YES", "on", "ON"]:
            monkeypatch.setenv("VERBOSE", truthy)
            result = resolver.get_bool("verbose", cli_value=None, env_key="VERBOSE", default=False)
            assert result is True, f"Expected '{truthy}' to be truthy"

    def test_get_bool_env_falsy_values(self, monkeypatch):
        """Env var falsy values."""
        resolver = ConfigResolver()
        for falsy in ["0", "false", "FALSE", "no", "NO", "off", "OFF", ""]:
            monkeypatch.setenv("VERBOSE", falsy)
            result = resolver.get_bool("verbose", cli_value=None, env_key="VERBOSE", default=False)
            assert result is False, f"Expected '{falsy}' to be falsy"

    def test_get_bool_default_fallback(self):
        """Default used when both CLI and env are None."""
        resolver = ConfigResolver()
        result = resolver.get_bool("verbose", cli_value=None, env_key="MISSING", default=True)
        assert result is True


class TestInputValidator:
    """Test schema validation at input boundaries."""

    def test_validate_symbols_json_valid(self):
        """Valid symbols JSON passes validation."""
        data = {"AAPL": {"last": 150.0, "dma20": 145.0}, "MSFT": {"last": 380.0}}
        result = InputValidator.validate_symbols_json(data)
        assert result == data

    def test_validate_symbols_json_not_dict(self):
        """Non-dict raises clear ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json("not a dict")

        assert "must be a dict/object" in str(exc.value)
        assert exc.value.field == "symbols"
        assert exc.value.details["actual_type"] == "str"

    def test_validate_symbols_json_empty(self):
        """Empty dict raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json({})

        assert "cannot be empty" in str(exc.value)
        assert exc.value.field == "symbols"

    def test_validate_symbols_json_invalid_symbol_key(self):
        """Non-string symbol key raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json({123: {"last": 150.0}})

        assert "Symbol keys must be strings" in str(exc.value)
        assert "123" in str(exc.value)

    def test_validate_symbols_json_invalid_features_type(self):
        """Non-dict features raises clear ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json({"AAPL": "not a dict"})

        assert "must have a dict/object value" in str(exc.value)
        assert "AAPL" in str(exc.value)
        assert exc.value.field == "symbols.AAPL"

    def test_validate_symbols_json_missing_last_field(self):
        """Missing 'last' field raises clear ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json({"AAPL": {"dma20": 145.0}})

        assert "missing required field 'last'" in str(exc.value)
        assert "AAPL" in str(exc.value)
        assert exc.value.field == "symbols.AAPL.last"
        assert "dma20" in str(exc.value.details["available_fields"])

    def test_validate_symbols_json_last_not_numeric(self):
        """Non-numeric 'last' field raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_symbols_json({"AAPL": {"last": "150.0"}})

        assert "must be a number" in str(exc.value)
        assert "AAPL" in str(exc.value)
        assert exc.value.field == "symbols.AAPL.last"

    def test_validate_features_json_valid(self):
        """Valid features JSON passes validation."""
        data = {"last": 150.0, "dma20": 145.0, "support": 140.0}
        result = InputValidator.validate_features_json(data)
        assert result == data

    def test_validate_features_json_not_dict(self):
        """Non-dict raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_features_json([1, 2, 3])

        assert "must be a dict/object" in str(exc.value)
        assert exc.value.field == "features"

    def test_validate_features_json_missing_last(self):
        """Missing 'last' field raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_features_json({"dma20": 145.0})

        assert "missing required field 'last'" in str(exc.value)
        assert exc.value.field == "features.last"

    def test_validate_profile_json_valid(self):
        """Valid profile JSON passes validation."""
        data = {"soft_cap": 100, "cooldown": 5, "used_lines": 10}
        result = InputValidator.validate_profile_json(data)
        assert result == data

    def test_validate_profile_json_missing_required(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            InputValidator.validate_profile_json({"soft_cap": 100})

        assert "missing required field 'cooldown'" in str(exc.value)
        assert exc.value.field == "profile.cooldown"


class TestSafeCopyAlerts:
    """Test defensive data copying patterns."""

    def test_safe_copy_alerts_creates_new_list(self):
        """Creates new list, not same reference."""
        original = [{"symbol": "AAPL", "price": 150.0}]
        copied = safe_copy_alerts(original)

        assert copied is not original
        assert copied == original

    def test_safe_copy_alerts_creates_new_dicts(self):
        """Each dict in list is copied."""
        original = [{"symbol": "AAPL", "price": 150.0}, {"symbol": "MSFT", "price": 380.0}]
        copied = safe_copy_alerts(original)

        assert copied[0] is not original[0]
        assert copied[1] is not original[1]
        assert copied[0] == original[0]
        assert copied[1] == original[1]

    def test_safe_copy_alerts_mutation_isolation(self):
        """Mutations to copy don't affect original."""
        original = [{"symbol": "AAPL", "price": 150.0}]
        copied = safe_copy_alerts(original)

        copied[0]["price"] = 999.0

        assert original[0]["price"] == 150.0
        assert copied[0]["price"] == 999.0

    def test_safe_copy_alerts_none_input(self):
        """None input returns empty list."""
        result = safe_copy_alerts(None)
        assert result == []

    def test_safe_copy_alerts_empty_list(self):
        """Empty list returns empty list."""
        result = safe_copy_alerts([])
        assert result == []


class TestConfigResolverIntegration:
    """Integration tests for realistic CLI scenarios."""

    def test_tws_connection_config_precedence(self, monkeypatch):
        """Test TWS connection config resolution (realistic scenario)."""
        # Set env vars (production defaults)
        monkeypatch.setenv("SENGOKU_TWS_HOST", "tws-prod.internal")
        monkeypatch.setenv("SENGOKU_TWS_PORT", "7496")
        monkeypatch.setenv("SENGOKU_TWS_CLIENT_ID", "100")

        resolver = ConfigResolver()

        # CLI overrides for local testing
        host = resolver.get_str("tws_host", cli_value="127.0.0.1", env_key="SENGOKU_TWS_HOST", default="127.0.0.1")
        port = resolver.get_int("tws_port", cli_value=4002, env_key="SENGOKU_TWS_PORT", default=7496)
        client_id = resolver.get_int(
            "tws_client_id", cli_value=None, env_key="SENGOKU_TWS_CLIENT_ID", default=107  # Falls back to env
        )

        assert host == "127.0.0.1"  # CLI override
        assert port == 4002  # CLI override
        assert client_id == 100  # Env var (no CLI override)

    def test_notify_config_boolean_flags(self, monkeypatch):
        """Test notify command boolean config resolution."""
        monkeypatch.setenv("SENGOKU_NOTIFY_REQUIRE_ACCEPT", "true")
        monkeypatch.setenv("SENGOKU_NOTIFY_READY_MIN", "70")

        resolver = ConfigResolver()

        require_accept = resolver.get_bool(
            "require_acceptance", cli_value=False, env_key="SENGOKU_NOTIFY_REQUIRE_ACCEPT", default=False  # CLI=False
        )
        ready_min = resolver.get_int(
            "ready_min", cli_value=None, env_key="SENGOKU_NOTIFY_READY_MIN", default=65  # Falls to env
        )

        assert require_accept is False  # CLI override wins
        assert ready_min == 70  # Env var used
