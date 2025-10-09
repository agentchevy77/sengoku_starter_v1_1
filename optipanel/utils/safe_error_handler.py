"""Fail-safe error handler utilities for logging and CLI workflows."""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ErrorMetrics:
    total_errors: int = 0
    recursion_prevented: int = 0
    logging_failures: int = 0
    stderr_fallbacks: int = 0
    circuit_breaker_trips: int = 0
    last_error_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_errors": self.total_errors,
            "recursion_prevented": self.recursion_prevented,
            "logging_failures": self.logging_failures,
            "stderr_fallbacks": self.stderr_fallbacks,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "last_error_time": self.last_error_time,
        }


class CircuitBreakerState:
    """Simple circuit-breaker used to avoid endless logging loops."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 5.0,
        half_open_success_threshold: int = 1,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if half_open_success_threshold < 1:
            raise ValueError("half_open_success_threshold must be >= 1")

        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.is_open = False

        self._lock = threading.Lock()
        self._opened_at: float | None = None
        self._half_open_successes = 0

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            self._half_open_successes = 0
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                self._opened_at = self.last_failure_time

    def record_success(self) -> None:
        with self._lock:
            if not self.is_open:
                self.failure_count = 0
                self._half_open_successes = 0
                return

            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_success_threshold:
                self.is_open = False
                self.failure_count = 0
                self._opened_at = None
                self._half_open_successes = 0

    def should_attempt(self) -> bool:
        with self._lock:
            if not self.is_open:
                return True

            if self.reset_timeout_seconds <= 0 or self._opened_at is None:
                return False

            elapsed = time.monotonic() - self._opened_at
            return elapsed >= self.reset_timeout_seconds

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "failure_threshold": self.failure_threshold,
                "reset_timeout_seconds": self.reset_timeout_seconds,
                "half_open_success_threshold": self.half_open_success_threshold,
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
                "is_open": self.is_open,
                "_opened_at": self._opened_at,
                "_half_open_successes": self._half_open_successes,
            }

    def restore(self, state: dict[str, Any]) -> None:
        with self._lock:
            self.failure_threshold = state["failure_threshold"]
            self.reset_timeout_seconds = state["reset_timeout_seconds"]
            self.half_open_success_threshold = state["half_open_success_threshold"]
            self.failure_count = state["failure_count"]
            self.last_failure_time = state["last_failure_time"]
            self.is_open = state["is_open"]
            self._opened_at = state["_opened_at"]
            self._half_open_successes = state["_half_open_successes"]


class SafeErrorHandler:
    """Fail-safe error logging that resists recursive failures."""

    MAX_RECURSION_DEPTH = 8

    _registry_lock = threading.RLock()
    _circuit_breakers: dict[str, CircuitBreakerState] = {}
    _metrics: dict[str, ErrorMetrics] = {}
    _handler_cache: dict[str, SafeErrorHandler] = {}

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        context: str | None = None,
        max_recursion: int | None = None,
    ) -> None:
        self.context = context or (logger.name if logger else "global")
        self.logger = logger or logging.getLogger(self.context)
        self.max_recursion = max_recursion if max_recursion is not None else self.MAX_RECURSION_DEPTH
        self._thread_state = threading.local()
        self._ensure_registry_entries()

    # ------------------------------------------------------------------ helpers
    def _ensure_registry_entries(self) -> None:
        with self._registry_lock:
            self._circuit_breakers.setdefault(self.context, CircuitBreakerState())
            self._metrics.setdefault(self.context, ErrorMetrics())
            cached = self._handler_cache.get(self.context)
            if cached is None or cached.logger is not self.logger:
                self._handler_cache[self.context] = self

    @property
    def _recursion_depth(self) -> int:
        return getattr(self._thread_state, "depth", 0)

    @_recursion_depth.setter
    def _recursion_depth(self, value: int) -> None:
        self._thread_state.depth = value

    @contextmanager
    def _recursion_guard(self) -> Iterator[bool]:
        depth = self._recursion_depth
        self._recursion_depth = depth + 1
        try:
            yield depth < self.max_recursion
        finally:
            self._recursion_depth = depth

    def _get_circuit_breaker(self) -> CircuitBreakerState:
        with self._registry_lock:
            breaker = self._circuit_breakers.get(self.context)
            if breaker is None:
                breaker = CircuitBreakerState()
                self._circuit_breakers[self.context] = breaker
            return breaker

    def _get_metrics(self) -> ErrorMetrics:
        with self._registry_lock:
            metrics = self._metrics.get(self.context)
            if metrics is None:
                metrics = ErrorMetrics()
                self._metrics[self.context] = metrics
            return metrics

    def _render_message(self, template: str, *args: Any, **kwargs: Any) -> str:
        if not args and not kwargs:
            return str(template)
        try:
            if args:
                return template % args
            return template.format(**kwargs)
        except Exception as exc:  # pragma: no cover
            return f"{template} (formatting failed: {exc})"

    def _resolve_exc_info(
        self,
        *,
        exc: BaseException | None,
        exc_info: bool | BaseException | tuple[type[BaseException], BaseException, Any] | None,
    ) -> Any:
        if exc is not None:
            return (type(exc), exc, exc.__traceback__)
        if isinstance(exc_info, tuple):
            return exc_info
        if isinstance(exc_info, BaseException):
            return (type(exc_info), exc_info, exc_info.__traceback__)
        if exc_info:
            info = sys.exc_info()
            return info if any(info) else True
        return False

    def _fallback_stderr(self, message: str, *, exc_info: Any = None) -> None:
        metrics = self._get_metrics()
        metrics.stderr_fallbacks += 1
        print(f"[ERROR] [{self.context}] {message}", file=sys.stderr)
        if exc_info:
            if exc_info is True:
                traceback.print_exc()
            elif isinstance(exc_info, BaseException):
                traceback.print_exception(type(exc_info), exc_info, exc_info.__traceback__)
            elif isinstance(exc_info, tuple):
                traceback.print_exception(*exc_info)
            else:
                traceback.print_exception(*sys.exc_info())

    # ----------------------------------------------------------------- API
    def handle_error(
        self,
        message: str,
        *fmt_args: Any,
        exc: BaseException | None = None,
        exc_info: bool | BaseException | tuple[type[BaseException], BaseException, Any] | None = None,
        **log_kwargs: Any,
    ) -> None:
        metrics = self._get_metrics()
        metrics.total_errors += 1
        metrics.last_error_time = time.time()

        formatted_message = self._render_message(message, *fmt_args)

        with self._recursion_guard() as can_proceed:
            if not can_proceed:
                metrics.recursion_prevented += 1
                self._fallback_stderr(formatted_message)
                return

            breaker = self._get_circuit_breaker()
            if not breaker.should_attempt():
                metrics.circuit_breaker_trips += 1
                self._fallback_stderr(formatted_message, exc_info=exc or exc_info)
                return

            resolved_exc_info = self._resolve_exc_info(exc=exc, exc_info=exc_info)

            try:
                if resolved_exc_info:
                    log_kwargs.setdefault("exc_info", resolved_exc_info)
                self.logger.error(formatted_message, **log_kwargs)
                breaker.record_success()
            except Exception as logging_failure:  # pragma: no cover
                breaker.record_failure()
                metrics.logging_failures += 1
                self._fallback_stderr(
                    formatted_message,
                    exc_info=exc if exc is not None else logging_failure,
                )

    def safe_exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.handle_error(message, *args, exc_info=True, **kwargs)

    # ----------------------------------------------------------------- metrics
    @classmethod
    def get_metrics(cls, context: str) -> dict[str, Any]:
        with cls._registry_lock:
            metrics = cls._metrics.setdefault(context, ErrorMetrics())
            return metrics.to_dict()

    @classmethod
    def reset_circuit_breaker(cls, context: str) -> None:
        with cls._registry_lock:
            cls._circuit_breakers[context] = CircuitBreakerState()

    @classmethod
    @contextmanager
    def configure_circuit_breaker(cls, context: str, **config: Any) -> Iterator[CircuitBreakerState]:
        with cls._registry_lock:
            breaker = cls._circuit_breakers.get(context)
            created = False
            if breaker is None:
                breaker = CircuitBreakerState()
                cls._circuit_breakers[context] = breaker
                created = True

            snapshot = breaker.snapshot()
            for key, value in config.items():
                if hasattr(breaker, key):
                    setattr(breaker, key, value)

        try:
            yield breaker
        finally:
            with cls._registry_lock:
                if created:
                    cls._circuit_breakers.pop(context, None)
                else:
                    breaker.restore(snapshot)

    # ----------------------------------------------------------------- helpers
    @classmethod
    def _get_or_create_handler(
        cls,
        context: str,
        *,
        logger: logging.Logger | None = None,
    ) -> SafeErrorHandler:
        with cls._registry_lock:
            handler = cls._handler_cache.get(context)
            if handler is None or (logger is not None and handler.logger is not logger):
                handler = SafeErrorHandler(logger=logger, context=context)
                cls._handler_cache[context] = handler
            return handler


def handle_error_safely(
    message: str,
    *,
    context: str = "global",
    exc: BaseException | None = None,
    exc_info: bool | BaseException | tuple[type[BaseException], BaseException, Any] | None = None,
    logger: logging.Logger | None = None,
    **log_kwargs: Any,
) -> None:
    handler = SafeErrorHandler._get_or_create_handler(context, logger=logger)
    handler.handle_error(message, exc=exc, exc_info=exc_info, **log_kwargs)


@contextmanager
def safe_error_context(
    *,
    logger: logging.Logger | None = None,
    context: str | None = None,
    suppress: bool = False,
) -> Iterator[None]:
    handler = SafeErrorHandler._get_or_create_handler(context or (logger.name if logger else "global"), logger=logger)
    try:
        yield
    except Exception as exc:
        handler.handle_error("Unhandled exception: %s", str(exc), exc=exc)
        if not suppress:
            raise


def safe_log_exception(
    logger: logging.Logger,
    message: str,
    *args: Any,
    context: str | None = None,
    **kwargs: Any,
) -> None:
    handler = SafeErrorHandler._get_or_create_handler(context or logger.name, logger=logger)
    handler.safe_exception(message, *args, **kwargs)


__all__: Iterable[str] = [
    "CircuitBreakerState",
    "ErrorMetrics",
    "SafeErrorHandler",
    "handle_error_safely",
    "safe_error_context",
    "safe_log_exception",
]
