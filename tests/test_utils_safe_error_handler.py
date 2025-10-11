"""
Comprehensive tests for optipanel/utils/safe_error_handler.py.
Restored during rollback recovery and adapted for the current API.
"""

from __future__ import annotations

import logging
import threading
import time
import unittest.mock as mock
import uuid
from collections.abc import Callable
from contextlib import redirect_stderr
from io import StringIO
from typing import Any

import pytest

try:
    from optipanel.utils.safe_error_handler import (
        CircuitBreakerState,
        ErrorMetrics,
        SafeErrorHandler,
        handle_error_safely,
    )
except ImportError:  # pragma: no cover
    pytest.skip("optipanel.utils.safe_error_handler not found", allow_module_level=True)

SEHClass = SafeErrorHandler


def _with_fallbacks(func: Callable[..., Any], *triplets: dict[str, Any]) -> Any:
    """Call func with the first kwargs mapping that works, respecting API drift."""
    last_error: Exception | None = None
    for kwargs in triplets:
        try:
            return func(**kwargs)
        except TypeError as exc:  # pragma: no cover - only hit if API drifts again
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("No call attempted")  # pragma: no cover


def _cleanup_context(context: str) -> None:
    with SafeErrorHandler._registry_lock:  # type: ignore[attr-defined]
        SafeErrorHandler._handler_cache.pop(context, None)  # type: ignore[attr-defined]
        SafeErrorHandler._metrics.pop(context, None)  # type: ignore[attr-defined]
        SafeErrorHandler._circuit_breakers.pop(context, None)  # type: ignore[attr-defined]


@pytest.fixture
def unique_context() -> str:
    return f"test_safe_error_handler_{uuid.uuid4()}"


@pytest.fixture
def error_handler(unique_context: str) -> SEHClass:
    handler = _with_fallbacks(
        SafeErrorHandler,
        {"context": unique_context, "max_recursion": 2},
        {"context": unique_context, "recursion_limit": 2},
        {"context": unique_context},
    )

    if not hasattr(handler, "max_recursion") and hasattr(handler, "recursion_limit"):
        handler.max_recursion = handler.recursion_limit  # type: ignore[attr-defined]

    breaker = handler._get_circuit_breaker()
    if hasattr(breaker, "failure_threshold"):
        breaker.failure_threshold = 3
    elif hasattr(breaker, "threshold"):
        breaker.threshold = 3  # pragma: no cover
    if hasattr(breaker, "reset_timeout_seconds"):
        breaker.reset_timeout_seconds = 0.05
    elif hasattr(breaker, "reset_period"):
        breaker.reset_period = 0.05  # pragma: no cover

    yield handler

    handler._recursion_depth = 0
    _cleanup_context(handler.context)


@pytest.fixture
def handler_fixture(
    error_handler: SEHClass, caplog: pytest.LogCaptureFixture
) -> tuple[SEHClass, pytest.LogCaptureFixture]:
    logger_instance = getattr(error_handler, "logger", logging.getLogger())
    logger_name = getattr(logger_instance, "name", None)
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        yield error_handler, caplog


def test_error_metrics_initial_state() -> None:
    metrics = ErrorMetrics()
    assert metrics.total_errors == 0
    assert getattr(metrics, "recursion_prevented", 0) == 0
    assert getattr(metrics, "circuit_breaker_trips", 0) == 0
    if hasattr(metrics, "to_dict"):
        assert isinstance(metrics.to_dict(), dict)
    elif hasattr(metrics, "as_dict"):  # pragma: no cover - legacy helper
        assert isinstance(metrics.as_dict(), dict)


def test_circuit_breaker_logic() -> None:
    breaker = _with_fallbacks(
        CircuitBreakerState,
        {"failure_threshold": 3, "reset_timeout_seconds": 0.05},
        {"threshold": 3, "reset_period": 0.05},  # pragma: no cover
    )

    assert breaker.should_attempt()
    for _ in range(3):
        breaker.record_failure()

    assert getattr(breaker, "is_open", False)
    assert not breaker.should_attempt()

    time.sleep(0.06)
    assert breaker.should_attempt()
    breaker.record_success()
    assert not getattr(breaker, "is_open", False)
    assert breaker.failure_count == 0


def test_handle_error_logging_updates_metrics(handler_fixture: tuple[SEHClass, pytest.LogCaptureFixture]) -> None:
    handler, caplog = handler_fixture
    exc = ValueError("Test error")

    handler.handle_error("Action failed", exc=exc)

    metrics = handler._get_metrics()
    assert metrics.total_errors == 1
    assert metrics.logging_failures == 0
    assert caplog.records, "Expected log record to be emitted"
    assert any("Action failed" in record.message for record in caplog.records)


def test_recursion_prevention_triggers_stderr(error_handler: SEHClass) -> None:
    recursion_limit = getattr(error_handler, "max_recursion", getattr(error_handler, "recursion_limit", 2))
    sink = StringIO()

    def recursive_failure(*args: object, **kwargs: object) -> None:
        error_handler.handle_error(
            "Nested failure depth=%s",
            getattr(error_handler, "_recursion_depth", -1),
            exc=RuntimeError("forced recursion"),
        )

    with redirect_stderr(sink), mock.patch.object(error_handler.logger, "error", side_effect=recursive_failure):
        error_handler.handle_error("Initial trigger")

    metrics = error_handler._get_metrics()
    assert metrics.total_errors >= recursion_limit
    assert metrics.recursion_prevented >= 1
    assert metrics.stderr_fallbacks >= 1
    stderr_output = sink.getvalue()
    assert error_handler.context in stderr_output
    assert ("Initial trigger" in stderr_output) or ("Nested failure" in stderr_output)


def test_circuit_breaker_integration(error_handler: SEHClass) -> None:
    breaker = error_handler._get_circuit_breaker()
    threshold = getattr(breaker, "failure_threshold", getattr(breaker, "threshold", 3))

    call_count = 0

    def failing_logger(*args: object, **kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("simulated logger failure")

    sink = StringIO()
    with redirect_stderr(sink), mock.patch.object(error_handler.logger, "error", side_effect=failing_logger):
        for attempt in range(threshold):
            error_handler.handle_error("Breaker attempt %s", attempt + 1, exc=IndexError("breaker test"))
        error_handler.handle_error("Breaker suppressed")

    assert call_count == threshold
    assert "Breaker suppressed" in sink.getvalue()

    metrics = error_handler._get_metrics()
    assert metrics.total_errors == threshold + 1
    assert metrics.logging_failures == threshold
    assert metrics.circuit_breaker_trips >= 1
    assert getattr(breaker, "is_open", False)

    time.sleep(0.06)
    error_handler.handle_error("Breaker recovered")
    assert not getattr(breaker, "is_open", False)


def test_recursion_depth_is_thread_local(error_handler: SEHClass) -> None:
    error_handler._recursion_depth = 4

    event = threading.Event()
    thread_depths: list[int] = []

    def worker() -> None:
        thread_depths.append(error_handler._recursion_depth)
        error_handler._recursion_depth = 1
        thread_depths.append(error_handler._recursion_depth)
        event.set()

    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    event.wait(timeout=1)
    worker_thread.join()

    assert thread_depths == [0, 1]
    assert error_handler._recursion_depth == 4
    error_handler._recursion_depth = 0


def test_handle_error_safely_keyword_usage(caplog: pytest.LogCaptureFixture, unique_context: str) -> None:
    context = f"{unique_context}_global"
    exc = RuntimeError("Global test")

    with caplog.at_level(logging.ERROR, logger=context):
        try:
            handle_error_safely(message="Global failure", context=context, exc=exc)
        except TypeError:  # pragma: no cover - legacy signature fallback
            handle_error_safely("Global failure", context=context, exc=exc)

    assert caplog.records
    assert any(record.message == "Global failure" for record in caplog.records)
    assert any(record.exc_info for record in caplog.records)

    metrics = SafeErrorHandler.get_metrics(context)
    assert metrics["total_errors"] == 1
    _cleanup_context(context)
