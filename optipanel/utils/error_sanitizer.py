"""
Error sanitization utility to prevent information disclosure in production environments.
(Addresses Bug #53)
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


class ErrorSanitizer:
    """
    Sanitizes exceptions, providing detailed logs for developers and safe messages for users.
    """

    def __init__(self, is_production: bool | None = None):
        if is_production is None:
            # Determine environment automatically
            env = os.getenv("SENGOKU_ENV", "development").lower()
            self.is_production = env in ("production", "prod")
        else:
            self.is_production = is_production

        # Define patterns for sensitive information (e.g., file paths)
        self._sensitive_patterns = [
            # Basic path obfuscation
            re.compile(r"(/[\w/.-]+/[\w.-]+)"),
        ]

    def sanitize(
        self,
        exception: Exception | str,
        context: str = "",
        safe_message: str = "An internal error occurred.",
    ) -> str:
        """
        Logs the exception with full context and returns a safe, sanitized message.
        """

        # Always log the full details for internal diagnostics
        self._log_exception(exception, context)

        error_message = str(exception) if isinstance(exception, Exception) else exception

        if self.is_production:
            # In production, apply sanitization
            sanitized_message = self._apply_patterns(error_message)
            if not sanitized_message.strip():
                sanitized_message = safe_message

            display_context = self._apply_patterns(context)
            if display_context:
                return f"{sanitized_message} (Context: {display_context})"
            return sanitized_message
        else:
            # In development, return a detailed message
            return self._format_detailed_message(error_message, context)

    def _apply_patterns(self, message: str) -> str:
        """Applies regex patterns to remove sensitive information."""
        if not isinstance(message, str):
            return "[REDACTED]"
        for pattern in self._sensitive_patterns:
            message = pattern.sub("[REDACTED]", message)
        return message

    def _log_exception(self, exception: Exception | str, context: str):
        """Internal method to log the exception traceback."""
        log_message = f"Sanitized Error encountered during '{context}'"

        if isinstance(exception, Exception):
            logger.error(f"{log_message}: {type(exception).__name__}", exc_info=exception)
        else:
            logger.error(f"{log_message}: {exception}")

    def _format_detailed_message(self, error_message: str, context: str) -> str:
        """Formats a detailed message for development environments."""
        msg = error_message.strip()
        return f"{msg} (in {context})" if context else msg


# Global instance for convenience (Used by cli/main.py)
_error_sanitizer = ErrorSanitizer()

# Expose the global instance and the class
__all__ = ["ErrorSanitizer", "_error_sanitizer"]
