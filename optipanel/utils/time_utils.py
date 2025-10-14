"""Time utilities with overflow and precision protection."""

import sys
import time


def get_safe_timestamp_ms() -> int:
    """Get millisecond timestamp safe from overflow.

    Returns:
        Millisecond timestamp as 64-bit int, safe from Year 2038 problem

    Notes:
        - Handles 32-bit systems
        - Prevents integer overflow
        - Safe for JavaScript interop (max 2^53-1)
    """
    timestamp_ms = time.time() * 1000

    # JavaScript MAX_SAFE_INTEGER = 2^53 - 1
    # This ensures compatibility when sending to browsers
    max_safe_integer = 9007199254740991

    # Convert to int and ensure within safe bounds
    timestamp_int = int(timestamp_ms)

    # Prevent overflow on 32-bit systems
    if sys.maxsize <= 2**31 - 1:
        # Force 64-bit representation
        timestamp_int = timestamp_int & 0xFFFFFFFFFFFFFFFF

    # Ensure within JavaScript safe integer range
    if timestamp_int > max_safe_integer:
        timestamp_int = timestamp_int % max_safe_integer

    return timestamp_int


def get_safe_timestamp_us() -> int:
    """Get microsecond timestamp safe from overflow.

    Returns:
        Microsecond timestamp as 64-bit int
    """
    timestamp_us = time.time() * 1000000
    return get_safe_int_from_float(timestamp_us)


def get_safe_int_from_float(value: float) -> int:
    """Safely convert float to int avoiding overflow.

    Args:
        value: Float value to convert

    Returns:
        Integer value within safe bounds
    """
    max_int64 = 2**63 - 1
    min_int64 = -(2**63)

    # Clamp to int64 bounds
    if value >= max_int64:
        return max_int64
    if value <= min_int64:
        return min_int64

    return int(value)


def safe_sleep(duration: float, min_duration: float = 0.0) -> None:
    """Sleep for duration with precision handling.

    Args:
        duration: Time to sleep in seconds
        min_duration: Minimum sleep time to avoid precision issues
    """
    epsilon = 1e-9

    # Skip sleep for negligible durations
    if duration < epsilon:
        return

    # Apply minimum duration if specified
    if min_duration > 0 and duration < min_duration:
        duration = min_duration

    time.sleep(duration)


def calculate_sleep_duration(interval: float, elapsed: float, buffer: float = 0.001) -> float:
    """Calculate sleep duration with precision handling.

    Args:
        interval: Target interval in seconds
        elapsed: Time already elapsed
        buffer: Small buffer to add (default 1ms)

    Returns:
        Sleep duration in seconds, or 0 if no sleep needed
    """
    epsilon = 1e-9

    remaining = interval - elapsed

    # No sleep needed if already past interval
    if remaining <= epsilon:
        return 0.0

    # Add buffer only if meaningful sleep is needed
    if remaining > buffer:
        return remaining + buffer
    else:
        return remaining


def compare_floats(a: float, b: float, epsilon: float = 1e-9) -> int:
    """Compare two floats with epsilon tolerance.

    Args:
        a: First value
        b: Second value
        epsilon: Tolerance for comparison

    Returns:
        -1 if a < b, 0 if equal within epsilon, 1 if a > b
    """
    diff = a - b

    if abs(diff) < epsilon:
        return 0
    elif diff < 0:
        return -1
    else:
        return 1


def is_zero(value: float, epsilon: float = 1e-9) -> bool:
    """Check if float is effectively zero.

    Args:
        value: Value to check
        epsilon: Tolerance for zero comparison

    Returns:
        True if value is within epsilon of zero

    Note:
        Handles both positive and negative zero correctly
    """
    return abs(value) < epsilon


__all__ = [
    "get_safe_timestamp_ms",
    "get_safe_timestamp_us",
    "get_safe_int_from_float",
    "safe_sleep",
    "calculate_sleep_duration",
    "compare_floats",
    "is_zero",
]
