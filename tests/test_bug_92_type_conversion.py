"""Regression tests for Bug #92: unvalidated type conversion chain in notify engine."""

from __future__ import annotations

import pytest

from optipanel.notify import engine


def test_update_bus_sanitises_tick_index_types() -> None:
    """Non-integer tick indices should be coerced safely without raising."""

    alerts = [
        {
            "symbol": "AAPL",
            "kind": "breach",
            "severity": "high",
            "message": "first",
            "value": 10,
            "threshold": 5,
        }
    ]

    bus: dict[tuple[str, str], dict[str, object]] = {}

    # Use deliberately malformed tick_index values
    engine.update_bus(bus, alerts, tick_index="7")
    engine.update_bus(bus, alerts, tick_index="invalid")

    entry = bus[("AAPL", "breach")]
    assert isinstance(entry["first_seen_tick"], int)
    assert isinstance(entry["last_seen_tick"], int)


def test_aggregate_alerts_handles_bad_tick_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sorting should remain stable even if last_seen_tick becomes non-numeric."""

    original_update_bus = engine.update_bus

    def poisoned_update_bus(bus, alerts, tick_index):  # type: ignore[override]
        original_update_bus(bus, alerts, tick_index)
        # Corrupt the last_seen_tick field to simulate historical bad data
        for event in bus.values():
            event["last_seen_tick"] = "not-an-int"

    monkeypatch.setattr(engine, "update_bus", poisoned_update_bus)

    runs = [
        {
            "alerts": [
                {"symbol": "AAPL", "kind": "breach", "severity": "high", "message": "first"},
                {"symbol": "MSFT", "kind": "breach", "severity": "medium", "message": "second"},
            ]
        }
    ]

    result = engine.aggregate_alerts(runs)

    assert result["counts"]["high"] >= 1
    assert result["counts"]["medium"] >= 1

    # Restore original implementation (monkeypatch handles automatically on teardown)
