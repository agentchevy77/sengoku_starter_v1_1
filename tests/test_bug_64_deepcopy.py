"""Regression tests for Bug #64: inconsistent deep copy in alert bus updates."""

from __future__ import annotations

import logging

import pytest

from optipanel.notify.engine import update_bus


def _base_alert() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "kind": "breach",
        "severity": "high",
        "message": "initial",
        "sustainment": {"window": [5, 10]},
        "supply": {"levels": [1, 2]},
        "gate": {"filters": {"min": 10}},
        "value": 10.0,
        "threshold": 5.0,
    }


def test_update_bus_stores_deep_copies() -> None:
    """Mutating the source alert after update must not affect the bus entry."""

    alert = _base_alert()
    alerts = [alert]
    bus: dict[tuple[str, str], dict[str, object]] = {}

    update_bus(bus, alerts, tick_index=0)

    entry = bus[("AAPL", "breach")]

    # Ensure new structures are not the same object as the source
    assert entry["sustainment"] is not alert["sustainment"]
    assert entry["supply"] is not alert["supply"]
    assert entry["gate"] is not alert["gate"]

    # Mutate the original alert payload
    alert["sustainment"]["window"].append(99)
    alert["supply"]["levels"].append(42)
    alert["gate"]["filters"]["min"] = 0

    # Bus entry remains unchanged
    assert entry["sustainment"] == {"window": [5, 10]}
    assert entry["supply"] == {"levels": [1, 2]}
    assert entry["gate"] == {"filters": {"min": 10}}


def test_update_bus_secondary_alert_does_not_share_state(caplog: pytest.LogCaptureFixture) -> None:
    """Follow-up alerts should also be isolated once copied into the bus."""

    first = _base_alert()
    bus: dict[tuple[str, str], dict[str, object]] = {}
    update_bus(bus, [first], tick_index=1)

    second = {
        "symbol": "AAPL",
        "kind": "breach",
        "severity": "medium",
        "message": "follow-up",
        # Provide higher magnitude so value/threshold get replaced
        "value": 50.0,
        "threshold": 10.0,
        "readiness": {"state": {"score": 3}},
    }

    with caplog.at_level(logging.WARNING, logger="optipanel.notify.engine"):
        update_bus(bus, [second], tick_index=2)

    entry = bus[("AAPL", "breach")]
    # Readiness copied from second alert, but deep copied
    assert entry["readiness"] == {"state": {"score": 3}}
    assert entry["readiness"] is not second["readiness"]

    # Modify second alert after update; bus should not change
    second["readiness"]["state"]["score"] = 999
    assert entry["readiness"] == {"state": {"score": 3}}
