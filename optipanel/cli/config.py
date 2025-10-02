"""Unified configuration and validation layer for CLI commands.

This module provides centralized configuration resolution and input validation
to eliminate inconsistencies and improve error messages at input boundaries.

Fixes:
- Bug #11: Inconsistent configuration logic across CLI commands
- Bug #12: Unsafe data mutation (defensive patterns)
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

T = TypeVar("T")


class ConfigResolver:
    """Centralized configuration resolver with clear precedence: CLI > ENV > default.

    This eliminates the inconsistent configuration patterns scattered across CLI commands.

    Examples:
        >>> resolver = ConfigResolver()
        >>> # CLI arg takes precedence
        >>> resolver.get_int("port", cli_value=8080, env_key="PORT", default=7496)
        8080
        >>> # Falls back to env var
        >>> os.environ["PORT"] = "9000"
        >>> resolver.get_int("port", cli_value=None, env_key="PORT", default=7496)
        9000
        >>> # Falls back to default
        >>> resolver.get_int("port", cli_value=None, env_key="MISSING", default=7496)
        7496
    """

    def get_str(
        self,
        name: str,
        cli_value: str | None,
        env_key: str | None = None,
        default: str = "",
    ) -> str:
        """Resolve string config with precedence: CLI > ENV > default."""
        # CLI argument takes precedence
        if cli_value is not None:
            return str(cli_value)

        # Environment variable second
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                return str(env_val)

        # Default last
        return default

    def get_int(
        self,
        name: str,
        cli_value: int | None,
        env_key: str | None = None,
        default: int = 0,
    ) -> int:
        """Resolve integer config with precedence: CLI > ENV > default."""
        # CLI argument takes precedence
        if cli_value is not None:
            return int(cli_value)

        # Environment variable second (with safe conversion)
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                try:
                    return int(env_val)
                except (ValueError, TypeError):
                    # Log warning but continue to default
                    import logging

                    logging.warning(
                        f"Config '{name}': Invalid integer in env var {env_key}='{env_val}', using default={default}"
                    )

        # Default last
        return default

    def get_float(
        self,
        name: str,
        cli_value: float | None,
        env_key: str | None = None,
        default: float = 0.0,
    ) -> float:
        """Resolve float config with precedence: CLI > ENV > default."""
        # CLI argument takes precedence
        if cli_value is not None:
            return float(cli_value)

        # Environment variable second (with safe conversion)
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                try:
                    return float(env_val)
                except (ValueError, TypeError):
                    import logging

                    logging.warning(
                        f"Config '{name}': Invalid float in env var {env_key}='{env_val}', using default={default}"
                    )

        # Default last
        return default

    def get_bool(
        self,
        name: str,
        cli_value: bool | None,
        env_key: str | None = None,
        default: bool = False,
    ) -> bool:
        """Resolve boolean config with precedence: CLI > ENV > default.

        Environment variable parsing is lenient: "1", "true", "yes", "on" = True (case-insensitive)
        """
        # CLI argument takes precedence
        if cli_value is not None:
            return bool(cli_value)

        # Environment variable second (with lenient parsing)
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                return self._parse_bool_env(env_val)

        # Default last
        return default

    @staticmethod
    def _parse_bool_env(value: str) -> bool:
        """Parse boolean from environment variable (lenient)."""
        if not value:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}


class ValidationError(Exception):
    """Clear validation error raised at input boundary.

    This provides much better error messages than KeyError/TypeError deep in business logic.
    """

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        self.field = field
        self.details = details or {}
        super().__init__(message)


class InputValidator:
    """Schema validation for CLI JSON inputs.

    Validates structure at input boundaries to provide clear error messages
    instead of cryptic failures deep in business logic.
    """

    @staticmethod
    def validate_symbols_json(data: Any) -> dict[str, dict[str, Any]]:
        """Validate symbols JSON has correct structure: {symbol: {features}}.

        Args:
            data: Raw JSON data from user input

        Returns:
            Validated symbols dictionary

        Raises:
            ValidationError: If structure is invalid with clear message

        Expected structure:
            {
                "AAPL": {"last": 150.0, "dma20": 145.0, ...},
                "MSFT": {"last": 380.0, "dma20": 375.0, ...},
                ...
            }
        """
        if not isinstance(data, dict):
            raise ValidationError(
                f"Symbols JSON must be a dict/object, got {type(data).__name__}. "
                f'Expected format: {{"AAPL": {{"last": 150.0, ...}}, "MSFT": {{...}}}}',
                field="symbols",
                details={"actual_type": type(data).__name__},
            )

        if not data:
            raise ValidationError(
                "Symbols JSON cannot be empty. " 'Expected format: {"AAPL": {"last": 150.0, ...}}',
                field="symbols",
            )

        # Validate each symbol entry
        for symbol, features in data.items():
            if not isinstance(symbol, str):
                raise ValidationError(
                    f"Symbol keys must be strings, got {type(symbol).__name__} for key {symbol!r}",
                    field=f"symbols.{symbol}",
                    details={"symbol": symbol, "type": type(symbol).__name__},
                )

            if not isinstance(features, dict):
                raise ValidationError(
                    f"Symbol '{symbol}' must have a dict/object value with features, got {type(features).__name__}. "
                    f'Expected format: "{symbol}": {{"last": 150.0, "dma20": 145.0, ...}}',
                    field=f"symbols.{symbol}",
                    details={"symbol": symbol, "actual_type": type(features).__name__},
                )

            # Validate critical fields exist (lenient - allows missing optionals)
            if "last" not in features:
                raise ValidationError(
                    f"Symbol '{symbol}' missing required field 'last' (current price). "
                    f'Expected format: "{symbol}": {{"last": 150.0, ...}}',
                    field=f"symbols.{symbol}.last",
                    details={"symbol": symbol, "available_fields": list(features.keys())},
                )

            # Validate last is numeric
            if not isinstance(features["last"], (int, float)):
                raise ValidationError(
                    f"Symbol '{symbol}' field 'last' must be a number, got {type(features['last']).__name__}",
                    field=f"symbols.{symbol}.last",
                    details={"symbol": symbol, "value": features["last"], "type": type(features["last"]).__name__},
                )

        return data

    @staticmethod
    def validate_features_json(data: Any) -> dict[str, Any]:
        """Validate features JSON for a single symbol.

        Args:
            data: Raw JSON data from user input

        Returns:
            Validated features dictionary

        Raises:
            ValidationError: If structure is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError(
                f"Features JSON must be a dict/object, got {type(data).__name__}. "
                f'Expected format: {{"last": 150.0, "dma20": 145.0, ...}}',
                field="features",
                details={"actual_type": type(data).__name__},
            )

        # Validate critical field
        if "last" not in data:
            raise ValidationError(
                "Features JSON missing required field 'last' (current price). "
                'Expected format: {"last": 150.0, "dma20": 145.0, ...}',
                field="features.last",
                details={"available_fields": list(data.keys())},
            )

        if not isinstance(data["last"], (int, float)):
            raise ValidationError(
                f"Field 'last' must be a number, got {type(data['last']).__name__}",
                field="features.last",
                details={"value": data["last"], "type": type(data["last"]).__name__},
            )

        return data

    @staticmethod
    def validate_profile_json(data: Any) -> dict[str, Any]:
        """Validate profile JSON for driver/budget commands.

        Expected structure:
            {
                "soft_cap": 100,
                "cooldown": 5,
                "used_lines": 10 or [1, 2, 3],
                "scan_stride_backoff": 2
            }
        """
        if not isinstance(data, dict):
            raise ValidationError(
                f"Profile JSON must be a dict/object, got {type(data).__name__}",
                field="profile",
                details={"actual_type": type(data).__name__},
            )

        # Validate required fields (lenient - allows additional fields)
        required = ["soft_cap", "cooldown"]
        for field in required:
            if field not in data:
                raise ValidationError(
                    f"Profile JSON missing required field '{field}'",
                    field=f"profile.{field}",
                    details={"available_fields": list(data.keys()), "required_fields": required},
                )

        return data


def safe_copy_alerts(alerts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Create defensive deep copy of alerts list before enrichment.

    This makes the defensive pattern explicit and prevents accidental mutations.

    Args:
        alerts: Original alerts list (may be None)

    Returns:
        Deep copy of alerts, or empty list if None
    """
    if not alerts:
        return []

    # Create new list with copied dicts (shallow copy of each dict is sufficient
    # since enrichment functions already do dict(alert) internally)
    return [dict(alert) for alert in alerts]
