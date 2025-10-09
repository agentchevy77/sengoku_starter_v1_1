"""Environment-aware error sanitiser used by CLI workflows (Bug #53)."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from typing import Any

from optipanel.cli.config import ValidationError

logger = logging.getLogger(__name__)

_GENERIC_MESSAGES: Mapping[type[BaseException], str] = {
    json.JSONDecodeError: "Invalid JSON syntax",
    ValidationError: "Validation failed",
    ValueError: "Invalid value provided",
    TypeError: "Invalid value provided",
}

_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"https?://[^\s]+"), "[URL_REDACTED]"),
    (re.compile(r"([A-Za-z]:)?[/\\][^\s]+"), "[PATH_REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL_REDACTED]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[IP_REDACTED]"),
    (re.compile(r"(?:ghp|gho|ghs|pat)_[A-Za-z0-9]{20,}"), "[TOKEN_REDACTED]"),
)


class ErrorSanitizer:
    """Sanitize exception messages for user-facing output."""

    def __init__(self, env: str | None = None, enable_redaction: bool | None = None) -> None:
        env_name = env or os.getenv("SENGOKU_ENV", "development")
        self._env = env_name.lower()
        if enable_redaction is None:
            enable_redaction = os.getenv("SENGOKU_ERROR_REDACTION", "").strip().lower() in {"1", "true", "yes"}
        self.enable_redaction = bool(enable_redaction or self.is_production)

    @property
    def is_production(self) -> bool:
        return self._env == "production"

    def sanitize(self, exc: BaseException, context: str | None = None) -> str:
        original_message = str(exc) if str(exc) else exc.__class__.__name__
        category = self._categorize(exc)

        if self.is_production:
            message = self._production_message(exc)
        else:
            message = original_message
            if self.enable_redaction:
                message = self._apply_redaction(message)

        if context:
            message = f"{message} in {context}" if self.is_production else f"{message} (in {context})"

        logger.error(
            "error_sanitizer category=%s type=%s message=%s context=%s",
            category,
            exc.__class__.__name__,
            original_message,
            context or "",
        )
        return message

    def get_safe_details(
        self,
        exc: BaseException,
        *,
        include_type: bool = False,
        include_message: bool = False,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {"category": self._categorize(exc)}
        if include_type:
            details["type"] = exc.__class__.__name__
        if include_message:
            details["message"] = self.sanitize(exc)
        return details

    def _production_message(self, exc: BaseException) -> str:
        for exc_type, msg in _GENERIC_MESSAGES.items():
            if isinstance(exc, exc_type):
                return msg
        return "An error occurred"

    def _categorize(self, exc: BaseException) -> str:
        if isinstance(exc, (json.JSONDecodeError, ValidationError)):
            return "validation"
        if isinstance(exc, OSError):
            return "system"
        return "runtime"

    def _apply_redaction(self, message: str) -> str:
        redacted = message
        for pattern, replacement in _REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


def sanitize_error_message(
    exc: BaseException,
    *,
    context: str | None = None,
    env: str | None = None,
) -> str:
    sanitizer = ErrorSanitizer(env=env)
    return sanitizer.sanitize(exc, context=context)


__all__ = ["ErrorSanitizer", "sanitize_error_message"]
