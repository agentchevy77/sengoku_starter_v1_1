from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from decimal import Decimal
from typing import Any

try:  # pragma: no cover - executed when Pydantic available
    from pydantic import BaseModel, ConfigDict, Field, field_validator

    PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback path when Pydantic missing
    logging.warning("Pydantic not installed. Alert validation will be degraded.")
    PYDANTIC_AVAILABLE = False

    class BaseModel:  # type: ignore[misc]
        def __init__(self, **data):
            self.__dict__.update(data)

        def model_dump(self, *args, **kwargs):
            return deepcopy(self.__dict__)

        @classmethod
        def model_validate(cls, data, *args, **kwargs):
            if isinstance(data, dict):
                return cls(**data)
            return cls()

    def _field(*args, **kwargs):
        return None

    def _field_validator(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    Field = _field  # type: ignore[misc]
    field_validator = _field_validator  # type: ignore[misc]

    ConfigDict = dict  # type: ignore[misc]


try:
    from optipanel.notify.utils import (
        invalid_symbol_token,
        normalize_severity,
        normalize_symbol,
    )
except ImportError as exc:  # pragma: no cover - fallback when notify.utils unavailable
    logging.error(
        "Failed to import normalization helpers from notify.utils: %s. Validation compromised.",
        exc,
    )

    def normalize_symbol(raw: Any) -> tuple[str, str | None]:
        return (str(raw).upper() if raw else "__MISSING__"), "import_error"

    def normalize_severity(severity: Any) -> str:
        return str(severity).lower() if severity else "info"

    def invalid_symbol_token(tag: str, source: str) -> str:
        return f"__INVALID_SYMBOL__{tag}"


try:
    from optipanel.utils.decimal_types import to_decimal
except ImportError:  # pragma: no cover - fallback when decimals helper missing

    def to_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
        try:
            return Decimal(str(value))
        except Exception:
            return default


logger = logging.getLogger(__name__)


class AlertPayload(BaseModel):
    """Validated and normalised alert payload."""

    if PYDANTIC_AVAILABLE:
        model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str = Field(..., description="Sanitised trading symbol")
    kind: str = Field(..., description="Alert kind")
    severity: str = Field(default="info", description="Normalised severity")
    message: str | None = Field(default=None)
    threshold: Any | None = Field(default=None)
    value: Any | None = Field(default=None)
    raw_symbol: str | None = Field(default=None)
    sustainment: dict[str, Any] | Any | None = Field(default=None)
    supply: dict[str, Any] | Any | None = Field(default=None)
    gate: dict[str, Any] | Any | None = Field(default=None)
    readiness: dict[str, Any] | Any | None = Field(default=None)

    if PYDANTIC_AVAILABLE:

        @field_validator("kind", mode="before")
        @classmethod
        def validate_kind(cls, value: Any) -> str:
            return "" if value is None else str(value).strip()

        @field_validator("severity", mode="before")
        @classmethod
        def validate_severity(cls, value: Any) -> str:
            return normalize_severity(value)

        @field_validator("threshold", "value", mode="before")
        @classmethod
        def validate_numeric(cls, value: Any) -> Any:
            if value is None:
                return None
            decimal_val = to_decimal(value, default=None)
            if decimal_val is not None:
                if isinstance(decimal_val, Decimal) and not decimal_val.is_finite():
                    logger.debug("Non-finite numeric value for alert field: %r", value)
                    return None
                return decimal_val
            logger.debug("Invalid numeric value for alert field: %r", value)
            return None

        @field_validator("symbol", mode="before")
        @classmethod
        def validate_symbol(cls, value: Any) -> str:
            return str(value) if value is not None else invalid_symbol_token("missing", "")

    @classmethod
    def parse_and_validate(cls, data: Any) -> AlertPayload | None:
        if not isinstance(data, Mapping):
            logger.error(
                "Alert payload must be a Mapping (e.g., dict), received %s",
                type(data).__name__,
            )
            return None

        if not PYDANTIC_AVAILABLE:
            return cls._fallback_parse(data)

        raw_payload = deepcopy(dict(data))

        raw_symbol_input = data.get("symbol")
        sanitized_symbol, issue = normalize_symbol(raw_symbol_input)
        prepared_data = dict(data)
        prepared_data["symbol"] = sanitized_symbol

        if issue and "raw_symbol" not in prepared_data:
            prepared_data["raw_symbol"] = "" if raw_symbol_input is None else str(raw_symbol_input)
            logger.warning(
                "notify.alert_model.symbol_normalized: original=%r sanitized=%s reason=%s",
                raw_symbol_input,
                sanitized_symbol,
                issue,
            )

        try:
            model = cls.model_validate(prepared_data)
            model._raw_payload = raw_payload
            return model
        except Exception as exc:
            logger.error(
                "Failed to validate alert payload for symbol %s: %s. Data (sample): %s",
                sanitized_symbol,
                exc,
                dict(list(prepared_data.items())[:5]),
            )
            return None

    @classmethod
    def _fallback_parse(cls, data: Mapping[str, Any]) -> AlertPayload | None:
        raw_payload = deepcopy(dict(data))
        instance = cls(**data)

        raw_symbol = getattr(instance, "symbol", None)
        symbol, issue = normalize_symbol(raw_symbol)
        instance.symbol = symbol
        instance.severity = normalize_severity(getattr(instance, "severity", None))
        instance.kind = str(getattr(instance, "kind", "")).strip()
        raw_value = getattr(instance, "value", None)
        raw_threshold = getattr(instance, "threshold", None)

        parsed_value = to_decimal(raw_value, default=None)
        parsed_threshold = to_decimal(raw_threshold, default=None)

        instance.value = parsed_value
        instance.threshold = parsed_threshold

        if issue and not getattr(instance, "raw_symbol", None):
            instance.raw_symbol = "" if raw_symbol is None else str(raw_symbol)

        instance._raw_payload = raw_payload
        return instance
