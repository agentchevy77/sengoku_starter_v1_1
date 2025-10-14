from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

# Attempt to import Pydantic components. Provide a graceful fallback if Pydantic
# is unavailable so the wider application can continue operating with minimal
# functionality (albeit without strict validation).
try:  # pragma: no cover - exercised implicitly when Pydantic present
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:  # pragma: no cover - fallback path
    logging.error("Pydantic not found. Data validation models will be inactive.")

    class BaseModel:  # type: ignore[misc]
        def model_dump(self, *args, **kwargs):
            return getattr(self, "__dict__", {})

        @classmethod
        def model_validate(cls, data, *args, **kwargs):
            instance = cls()
            if isinstance(data, dict):
                instance.__dict__.update(data)
            return instance

    class Field:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            pass

    ConfigDict = dict  # type: ignore[misc]


logger = logging.getLogger(__name__)


def convert_to_decimal(value: Any) -> Decimal:
    """Convert the incoming value to a finite :class:`Decimal`.

    Raises ``ValueError`` when conversion fails or the number is non-finite.
    This mirrors the hardening performed for Bug #36, ensuring downstream
    computations never receive invalid numeric inputs.
    """

    if value is None:
        raise ValueError("Value is None")

    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, float):
        if value == float("inf") or value == float("-inf") or value != value:
            raise ValueError(f"Value is not finite: {value}")
        result = Decimal(str(value))
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid format for Decimal: {value}") from exc
    else:
        raise TypeError(f"Unsupported type for Decimal conversion: {type(value)}")

    if not result.is_finite():
        raise ValueError(f"Value is not finite: {value}")

    return result


class BaseFeatureBundle(BaseModel):
    """Sparse market data feature set used for raw ingestion.

    All fields are optional. Non-finite or invalid entries are skipped rather
    than raising, preserving the lenient behaviour of the previous helper
    functions while benefiting from structured data access.
    """

    last: Decimal | None = Field(None)
    dma20: Decimal | None = Field(None)
    support: Decimal | None = Field(None)
    resistance: Decimal | None = Field(None)
    rvol: Decimal | None = Field(None)
    rs_strength: Decimal | None = Field(None)
    vwap_diff: Decimal | None = Field(None)

    model_config = ConfigDict(extra="allow")

    @classmethod
    def parse_sparse(cls, data: Any) -> BaseFeatureBundle:
        """Parse a potentially sparse mapping into a validated bundle."""

        if not isinstance(data, dict):
            if data is not None:
                logger.warning("Input data for parse_sparse is not a dictionary: %s", type(data))
            return cls()

        validated: dict[str, Any] = {}
        for key, value in data.items():
            if key in cls.model_fields:
                if value is None:
                    continue
                try:
                    validated[key] = convert_to_decimal(value)
                except (ValueError, TypeError) as exc:
                    logger.debug("Skipping invalid feature %s: %s (%s)", key, value, exc)
            else:
                validated[key] = value

        return cls.model_validate(validated)


class ValidatedFeatureBundle(BaseFeatureBundle):
    """Strict feature bundle guaranteeing all required metrics are present."""

    last: Decimal
    dma20: Decimal
    support: Decimal
    resistance: Decimal
    rvol: Decimal
    rs_strength: Decimal
    vwap_diff: Decimal

    model_config = ConfigDict(extra="allow")
