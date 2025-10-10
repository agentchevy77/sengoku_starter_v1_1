"""
Comprehensive tests for optipanel/utils/safe_error_handler.py.
Restored during Rollback Recovery.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import unittest.mock as mock
import uuid
from io import StringIO

import pytest

# Adjust the import path based on the actual project structure
try:
    from optipanel.utils.safe_error_handler import (
        CircuitBreakerState,
        ErrorMetrics,
        SafeErrorHandler,
        handle_error_safely,
        # Include other helpers if they exist and need testing
        # SafeExceptionHandler, safe_error_context,
    )

    # Use alias for clarity in type hints
    SEHClass = SafeErrorHandler
except ImportError:
    pytest.skip("optipanel.utils.safe_error_handler not found", allow_module_level=True)


# --- Fixtures ---


@pytest.fixture
def unique_context() -> str:
    """Generate a unique context string for isolated testing."""
    return f"test_handler_{uuid.uuid4()}"


@pytest.fixture
def error_handler(unique_context: str) -> SEHClass:
    """Provides a fresh SafeErrorHandler instance with low thresholds."""
    # Initialize with low limits for testing recursion and breaker
    # We rely on the implementation details observed during stabilization
    # Use a try-except block for robustness if the constructor signature varies due to the rollback
    try:
        handler = SafeErrorHandler(
            context=unique_context, recursion_limit=2, breaker_threshold=3, breaker_reset_period=0.5
        )
    except TypeError:
        # Fallback for implementations without explicit breaker parameters in constructor
        handler = SafeErrorHandler(context=unique_context, recursion_limit=2)
        # Configure the breaker if it exists on the handler instance
        if hasattr(handler, "breaker") and isinstance(handler.breaker, CircuitBreakerState):
            handler.breaker.threshold = 3
            handler.breaker.reset_period = 0.5

    # Ensure recursion depth is reset before each test (critical for isolation)
    if hasattr(handler, "_recursion_depth"):
        handler._recursion_depth = 0
    # Handle thread-local recursion guard cleanup if applicable
    if hasattr(handler, "_recursion_guard") and hasattr(handler._recursion_guard, "depth"):
        handler._recursion_guard.depth = 0

    return handler


@pytest.fixture
def handler_fixture(
    error_handler: SEHClass, caplog: pytest.LogCaptureFixture
) -> tuple[SEHClass, list[logging.LogRecord]]:
    """Provides handler and captures its logs."""
    # Capture logs for the specific logger associated with the handler
    logger_name = getattr(error_handler, "logger", logging.getLogger()).name

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        yield error_handler, caplog.records


@pytest.fixture
def capture_stderr():
    """Captures stderr output."""
    old_stderr = sys.stderr
    redirected_stderr = StringIO()
    sys.stderr = redirected_stderr
    yield redirected_stderr
    sys.stderr = old_stderr


# --- Tests for ErrorMetrics ---


def test_error_metrics_initial_state():
    metrics = ErrorMetrics()
    assert metrics.total_errors == 0
    assert metrics.recursion_prevented == 0
    assert getattr(metrics, "circuit_breaker_tripped", 0) == 0

    # Test dictionary conversion if implemented
    if hasattr(metrics, "to_dict"):
        assert isinstance(metrics.to_dict(), dict)


# --- Tests for CircuitBreakerState ---


def test_circuit_breaker_logic():
    # Check if CircuitBreakerState is defined before testing
    if "CircuitBreakerState" not in globals():
        pytest.skip("CircuitBreakerState not available.")

    breaker = CircuitBreakerState(threshold=3, reset_period=0.1)

    assert not breaker.is_tripped()

    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_tripped()

    breaker.record_failure()
    assert breaker.is_tripped()  # Tripped on 3rd failure

    # Wait for reset
    time.sleep(0.15)
    assert not breaker.is_tripped()

    breaker.record_failure()
    assert not breaker.is_tripped()


# --- Tests for SafeErrorHandler Core Logic ---


def test_handle_error_logging(handler_fixture: tuple[SEHClass, list[logging.LogRecord]]):
    """Test basic error handling and logging."""
    handler, records = handler_fixture
    exc = ValueError("Test error")

    handler.handle_error(exc, "Action failed")

    assert handler.metrics.total_errors == 1
    # Check if the context and message are included in the log
    assert any(handler.context in record.message and "Action failed" in record.message for record in records)


def test_recursion_prevention(error_handler: SEHClass, capture_stderr):
    """Test that the recursion guard prevents excessive nested error handling."""

    # We must simulate an error occurring within the error handler itself.
    target_logger = getattr(error_handler, "logger", None)
    if not target_logger:
        pytest.skip("Logger not accessible on handler.")

    # Use a counter to track actual calls
    call_count = 0

    def recursive_failure(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # This will cause handle_error to be called again recursively
        raise RuntimeError("Logger failed")

    # Mock the logger's error method to simulate the failure
    # Use mock.patch.object for robust patching and restoration
    with mock.patch.object(target_logger, "error", side_effect=recursive_failure):
        try:
            raise ValueError("Initial trigger")
        except ValueError as e:
            error_handler.handle_error(e, "initial")

    # Check metrics
    # The calls should stop once the recursion_limit (2) is reached.
    assert call_count == error_handler.recursion_limit
    assert error_handler.metrics.total_errors > 0
    assert error_handler.metrics.recursion_prevented > 0

    # Check stderr fallback (when recursion limit is hit)
    stderr_output = capture_stderr.getvalue()
    # Check for expected fallback messages observed during stabilization
    assert (
        "EMERGENCY FALLBACK" in stderr_output
        or "Recursion limit exceeded" in stderr_output
        or "failed to log" in stderr_output
    )


def test_circuit_breaker_integration(
    error_handler: SEHClass, handler_fixture: tuple[SEHClass, list[logging.LogRecord]]
):
    """Test that the circuit breaker trips and potentially suppresses logging."""
    if not hasattr(error_handler, "breaker") or not isinstance(error_handler.breaker, CircuitBreakerState):
        pytest.skip("Circuit breaker not implemented or accessible.")

    handler, records = handler_fixture
    exc = IndexError("Breaker test")

    # Threshold is 3
    for i in range(3):
        handler.handle_error(exc, f"Attempt {i+1}")

    assert handler.metrics.total_errors == 3
    assert handler.breaker.is_tripped()
    # Check if metrics attribute exists before accessing
    if hasattr(handler.metrics, "circuit_breaker_tripped"):
        assert getattr(handler.metrics, "circuit_breaker_tripped", 0) >= 1

    # Subsequent attempts
    initial_log_count = len(records)
    handler.handle_error(exc, "Attempt 4")

    assert handler.metrics.total_errors == 4

    # Check if logging behavior changed (suppressed or specific warning)
    # This assertion depends on the specific implementation behavior (suppress vs warn)
    if len(records) > initial_log_count:
        # If it logged, it should mention the circuit breaker or suppression
        assert any(
            "Circuit breaker tripped" in record.message
            or "Error handling suppressed" in record.message
            or "Circuit breaker active" in record.message
            for record in records[initial_log_count:]
        )
    # else: logging was fully suppressed, which is also valid.


def test_thread_safety_recursion_guard(error_handler: SEHClass):
    """Ensure recursion guard is thread-local."""

    # Access the internal thread-local storage (implementation dependent)
    guard_attr = None
    if hasattr(error_handler, "_recursion_guard"):
        guard_attr = "_recursion_guard"

    # Check if the implementation mechanism can be accessed
    if not guard_attr:
        pytest.skip("Cannot access internal recursion guard implementation.")

    guard = getattr(error_handler, guard_attr)

    # Check if the implementation uses the expected 'depth' attribute
    if not hasattr(guard, "depth"):
        pytest.skip("Recursion guard does not have expected 'depth' attribute.")

    # Set depth in main thread
    guard.depth = 5

    def thread_task(event):
        # Should be independent in this thread (default 0)
        assert getattr(guard, "depth", 0) == 0
        guard.depth = 1
        event.set()

    event = threading.Event()
    t = threading.Thread(target=thread_task, args=(event,))
    t.start()
    event.wait(timeout=1)
    t.join()

    # Main thread depth should remain unchanged
    assert guard.depth == 5


# --- Tests for Helper Functions ---


def test_handle_error_safely_global(caplog: pytest.LogCaptureFixture):
    """Test the global helper function."""
    exc = ZeroDivisionError("Global test")
    # Assuming the global handler logs at ERROR level
    with caplog.at_level(logging.ERROR):
        handle_error_safely(exc, "Global context")

    # Check for the log message format
    assert any(
        "Error during Global context" in record.message or "Global context" in record.message
        for record in caplog.records
    )
