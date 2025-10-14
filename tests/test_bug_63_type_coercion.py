"""Regression tests for Bug #63: alert payload type coercion vulnerability."""

from __future__ import annotations

import logging

import pytest

from optipanel.notify.engine import update_bus


def test_update_bus_rejects_string_payload(caplog: pytest.LogCaptureFixture) -> None:
    """String inputs must be rejected instead of iterated character by character."""

    bus: dict[tuple[str, str], dict[str, object]] = {}

    with caplog.at_level(logging.ERROR, logger="optipanel.notify.engine"):
        update_bus(bus, "CRITICAL", tick_index=0)

    assert bus == {}
    assert any("expected iterable of alert mappings" in message for message in caplog.messages)


def test_update_bus_skips_non_mapping_entries(caplog: pytest.LogCaptureFixture) -> None:
    """Non-mapping entries should be skipped without corrupting the bus."""

    bus: dict[tuple[str, str], dict[str, object]] = {}
    alerts = [
        {"symbol": "AAPL", "kind": "alert", "severity": "high", "message": "test"},
        42,
        None,
    ]

    with caplog.at_level(logging.ERROR, logger="optipanel.notify.engine"):
        update_bus(bus, alerts, tick_index=5)

    assert len(bus) == 1
    stored = next(iter(bus.values()))
    assert stored["symbol"] == "AAPL"
    assert stored["kind"] == "alert"
    # Ensure error about unsupported type was logged
    assert any("unsupported type" in message for message in caplog.messages)
