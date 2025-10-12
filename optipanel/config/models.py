"""
Pydantic models for application configuration.
Provides validation, type safety, and clear structure for configuration management.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, field_validator

D = Decimal


class TwsConfigModel(BaseModel):
    """Configuration for TWS connection and behavior."""

    host: str = Field(default="127.0.0.1", description="TWS Host Address")
    port: int = Field(default=7496, description="TWS Port", ge=1024, le=65535)
    client_id: int = Field(default=1, description="TWS Client ID", ge=0)
    rate_limit: float = Field(default=10.0, description="Requests per second pacing", gt=0)
    ref_symbol: str = Field(default="SPY", description="Reference symbol for market context")
    connect_timeout: float = Field(default=10.0, description="Timeout for connection (seconds)", gt=0)

    model_config = ConfigDict(extra="allow")


class UIConfigModel(BaseModel):
    """Configuration for the Textual TUI."""

    refresh_interval: float = Field(default=5.0, description="UI refresh cadence (seconds)", gt=0)
    refresh_timeout: float = Field(default=30.0, description="Timeout for refresh operations (seconds)", gt=0)

    model_config = ConfigDict(extra="allow")


class SetupConfigModel(BaseModel):
    """Configuration thresholds for strategy setups."""

    breakout_threshold: D = Field(default=D("0.7"), ge=0, le=1)
    breakdown_threshold: D = Field(default=D("0.7"), ge=0, le=1)
    trend_threshold: D = Field(default=D("0.5"), ge=0, le=1)
    exhaustion_threshold: D = Field(default=D("0.8"), ge=0, le=1)
    fakeout_risk_threshold: D = Field(default=D("0.6"), ge=0, le=1)
    sustainability_threshold: D = Field(default=D("0.4"), ge=0, le=1)
    breakout_gap_min: D = Field(default=D("0.01"), ge=0)
    breakdown_gap_min: D = Field(default=D("0.01"), ge=0)

    model_config = ConfigDict(extra="allow")

    # Serialize Decimal fields as strings for JSON output to preserve precision.
    @field_serializer("*", when_used="json")
    def serialize_decimal(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        return value

    @field_validator("*", mode="before")
    @classmethod
    def convert_to_decimal(cls, value: Any) -> Any:
        """Convert numeric-like inputs (str/float/int) to Decimal."""
        if isinstance(value, (float, int, str)):
            try:
                return D(str(value))
            except Exception:  # pragma: no cover - defer to Pydantic error reporting
                return value
        return value


class AppConfigModel(BaseModel):
    """Top-level application configuration."""

    tws: TwsConfigModel = Field(default_factory=TwsConfigModel)
    ui: UIConfigModel = Field(default_factory=UIConfigModel)
    setups: SetupConfigModel = Field(default_factory=SetupConfigModel)
    runtime_dirs: dict[str, str] | None = None

    model_config = ConfigDict(extra="allow")


if __name__ == "__main__":  # pragma: no cover - manual verification harness
    import pydantic

    print(f"Pydantic Version: {pydantic.VERSION}\n")
    try:
        config = AppConfigModel()
        print("Default configuration validated successfully:")
        print(config.model_dump_json(indent=2))

        custom_data = {
            "tws": {"host": "192.168.1.100", "rate_limit": 20.0},
            "ui": {"refresh_interval": 2.0},
            "setups": {"trend_threshold": 0.65},
        }
        custom_config = AppConfigModel(**custom_data)
        print("\nCustom configuration (dictionary dump):")
        print(custom_config.model_dump(exclude_unset=True))

        assert isinstance(custom_config.setups.trend_threshold, Decimal)
        assert custom_config.setups.trend_threshold == D("0.65")
        print("\nDecimal conversion verified.")
    except ValidationError as exc:  # pragma: no cover - manual verification harness
        print(f"Configuration validation failed:\n{exc}")


__all__ = [
    "AppConfigModel",
    "TwsConfigModel",
    "UIConfigModel",
    "SetupConfigModel",
    "D",
]
