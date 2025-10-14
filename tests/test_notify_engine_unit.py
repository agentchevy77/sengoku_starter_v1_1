"""
Comprehensive unit tests for optipanel/notify/engine.py.
Part 1: Normalization and Helper Functions.
"""

from __future__ import annotations

import hashlib
import logging
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest

try:
    from optipanel.notify.engine import (
        AlertEvent,
        AlertIndex,
        _safe_magnitude,
        aggregate_alerts,
        update_bus,
    )
    from optipanel.notify.utils import (
        _SEV_RANK,
        _SYMBOL_PLACEHOLDER,
    )
    from optipanel.notify.utils import (
        invalid_symbol_token as _invalid_symbol_token,
    )
    from optipanel.notify.utils import (
        normalize_severity as _normalize_severity,
    )
    from optipanel.notify.utils import (
        normalize_symbol as _normalize_symbol,
    )
    from optipanel.notify.utils import (
        severity_rank as _rank,
    )
except ImportError:  # pragma: no cover - test skipped when module missing
    pytest.skip("optipanel.notify.engine not found", allow_module_level=True)


@pytest.mark.parametrize(
    "raw_input, expected_symbol, expected_issue",
    [
        ("AAPL", "AAPL", None),
        ("GOOG.B", "GOOG.B", None),
        ("ES/F", "ES/F", None),
        ("BTC-USD", "BTC-USD", None),
        ("USER@HOST", "USER@HOST", None),
        ("A^B", "A^B", None),
        ("A_B", "A_B", None),
        ("aapl", "AAPL", None),
        ("  SPY  ", "SPY", "whitespace"),
        ("\tTSLA\n", "TSLA", "whitespace"),
        (None, _invalid_symbol_token("missing", ""), "missing"),
        ("", _invalid_symbol_token("empty", ""), "empty"),
        ("   ", _invalid_symbol_token("empty", ""), "empty"),
        ("A" * 48, "A" * 48, None),
        ("A" * 49, _invalid_symbol_token("toolong", "A" * 49), "too_long"),
        ("AAPL$", "AAPL", "invalid_suffix"),
        ("!NVDA", _invalid_symbol_token("badchar", "!NVDA"), "invalid_chars"),
        ("META(B)", _invalid_symbol_token("badchar", "META(B)"), "invalid_chars"),
        ("QQQ\n", "QQQ", "whitespace"),
        ("AMZN\x00", "AMZN", "invalid_suffix"),
        ("IBM STOCK", _invalid_symbol_token("badchar", "IBM STOCK"), "invalid_chars"),
        (123, "123", None),
    ],
)
def test_normalize_symbol(raw_input: Any, expected_symbol: str, expected_issue: str | None) -> None:
    symbol, issue = _normalize_symbol(raw_input)
    assert symbol == expected_symbol
    assert issue == expected_issue


def test_invalid_symbol_token_determinism() -> None:
    source = "complex*input"
    digest_source = source.encode("utf-8", "ignore")
    expected_digest = hashlib.sha1(digest_source).hexdigest().upper()[:6]
    assert _invalid_symbol_token("test", source) == f"{_SYMBOL_PLACEHOLDER}-TEST-{expected_digest}"

    fallback_digest = hashlib.sha1("TAG".encode("ascii")).hexdigest().upper()[:6]
    assert _invalid_symbol_token("tag", "") == f"{_SYMBOL_PLACEHOLDER}-TAG-{fallback_digest}"


@pytest.mark.parametrize(
    "raw_input, expected_severity, expected_rank",
    [
        ("high", "high", 3),
        ("HIGH", "high", 3),
        ("medium", "medium", 2),
        ("Medium", "medium", 2),
        ("low", "low", 1),
        ("info", "info", 1),
        (" high ", "high", 3),
        (None, "info", 1),
        ("", "info", 1),
        ("critical", "info", 1),
        (123, "info", 1),
    ],
)
def test_normalize_severity_and_rank(
    raw_input: Any,
    expected_severity: str,
    expected_rank: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="optipanel.notify.utils"):
        severity = _normalize_severity(raw_input)

    assert severity == expected_severity
    assert _rank(severity) == expected_rank

    normalized_key = str(raw_input).strip().lower() if raw_input is not None else ""
    if normalized_key and normalized_key not in _SEV_RANK:
        assert any("unknown severity" in record.message for record in caplog.records)


def test_normalize_severity_error_handling(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenStr:
        def __str__(self):
            raise TypeError("Cannot convert to string")

    with caplog.at_level(logging.ERROR, logger="optipanel.notify.utils"):
        result = _normalize_severity(BrokenStr())

    assert result == "info"
    assert any("conversion failed" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "value, threshold, expected",
    [
        (10, 5, 5.0),
        (5, 10, 5.0),
        (-5, 5, 10.0),
        (10.5, 8.2, 2.3),
        (10, None, 10.0),
        (None, 5, 5.0),
        (None, None, 0.0),
    ],
)
def test_safe_magnitude_valid(value: Any, threshold: Any, expected: float) -> None:
    magnitude = _safe_magnitude(value, threshold)
    assert magnitude == pytest.approx(expected)


@pytest.mark.parametrize(
    "value, threshold, expected_error",
    [
        ("invalid", 10, "ValueError"),
        (10, "invalid", "ValueError"),
        ({"a": 1}, 10, "TypeError"),
    ],
)
def test_safe_magnitude_invalid(
    value: Any,
    threshold: Any,
    expected_error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    context = "ctx"
    with caplog.at_level(logging.ERROR):
        result = _safe_magnitude(value, threshold, context=context)

    assert result is None
    assert any(
        f"notify.magnitude_calc_failed ({context})" in record.message and f"error={expected_error}" in record.message
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# AlertIndex fixtures


@pytest.fixture
def sample_events():
    return deepcopy(
        [
            {
                "symbol": "AAPL",
                "kind": "breach",
                "severity": "high",
                "last_seen_tick": 10,
                "value": 150,
                "threshold": 140,
            },
            {
                "symbol": "MSFT",
                "kind": "trend",
                "severity": "medium",
                "last_seen_tick": 5,
                "value": 300,
                "threshold": 290,
            },
            {"symbol": "SPY", "kind": "status", "severity": "info", "last_seen_tick": 10},
            {
                "symbol": "GOOG",
                "kind": "info",
                "severity": "low",
                "last_seen_tick": 8,
                "value": 2800,
                "threshold": 2700,
            },
            {"symbol": "QQQ", "kind": "status", "severity": "", "last_seen_tick": 10},
            {"symbol": "IBM!", "kind": "sanitized", "severity": "high", "message": "I1", "last_seen_tick": 2},
        ]
    )


@pytest.fixture
def alert_index(sample_events):
    return AlertIndex(sample_events)


def test_alert_index_initialization_and_lazy_build(alert_index: AlertIndex) -> None:
    assert getattr(alert_index, "_indexed", False) is False
    assert len(alert_index.all_events()) == 6
    assert alert_index._indexed is False
    alert_index._build_indexes()
    assert alert_index._indexed is True


def test_alert_index_empty_init() -> None:
    idx_none = AlertIndex(None)
    assert idx_none.all_events() == []
    assert idx_none.stats()["total_events"] == 0

    idx_empty = AlertIndex([])
    assert idx_empty.stats()["total_events"] == 0


def test_alert_index_by_symbol(alert_index: AlertIndex) -> None:
    assert len(alert_index.by_symbol("AAPL")) == 1

    ibm_alerts = alert_index.by_symbol("IBM")
    assert len(ibm_alerts) == 1
    assert ibm_alerts[0]["message"] == "I1"

    assert alert_index.by_symbol("UNKNOWN") == []


def test_alert_index_by_kind(alert_index: AlertIndex) -> None:
    status_alerts = alert_index.by_kind("status")
    assert len(status_alerts) == 2
    assert {alert["symbol"] for alert in status_alerts} == {"SPY", "QQQ"}

    assert alert_index.by_kind("unknown_kind") == []


def test_alert_index_by_severity(alert_index: AlertIndex) -> None:
    assert len(alert_index.by_severity("high")) == 2
    assert len(alert_index.by_severity("MEDIUM")) == 1

    info_alerts = alert_index.by_severity("info")
    assert len(info_alerts) == 1
    assert info_alerts[0]["symbol"] == "SPY"

    empty_alerts = alert_index.by_severity("")
    assert len(empty_alerts) == 1
    assert empty_alerts[0]["symbol"] == "QQQ"

    assert alert_index.by_severity("unknown") == []
    assert len(alert_index.by_severity(None)) == 1
    assert alert_index.by_severity("none") == []


def test_alert_index_utility_methods(alert_index: AlertIndex) -> None:
    assert set(alert_index.symbols()) == {"AAPL", "MSFT", "SPY", "GOOG", "QQQ", "IBM"}
    assert set(alert_index.kinds()) == {"breach", "trend", "status", "info", "sanitized"}
    assert set(alert_index.severities()) == {"high", "medium", "info", "low", ""}


def test_alert_index_stats(alert_index: AlertIndex) -> None:
    stats = alert_index.stats()
    assert stats["total_events"] == 6
    assert stats["unique_symbols"] == 6
    assert stats["unique_kinds"] == 5

    breakdown = stats["severity_breakdown"]
    assert breakdown["high"] == 2
    assert breakdown["medium"] == 1
    assert breakdown["low"] == 1
    assert breakdown["info"] == 2
    assert "" not in breakdown


def test_alert_index_symbol_normalization_logging(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="optipanel.notify.engine"):
        index = AlertIndex([{"symbol": "BAD$", "kind": "test"}])
        index._build_indexes()

    assert "BAD" in index.symbols()
    assert any("symbol_normalized" in record.message and "sanitized=BAD" in record.message for record in caplog.records)

    event = index.by_symbol("BAD")[0]
    assert event.get("raw_symbol") == "BAD$"


# Helper for creating a mock alert structure
def mock_alert(symbol, kind, severity="medium", value=10, threshold=5, message="Test", **kwargs):
    alert = {
        "symbol": symbol,
        "kind": kind,
        "severity": severity,
        "value": value,
        "threshold": threshold,
        "message": message,
    }
    alert.update(kwargs)
    return alert


class MutableFloat:
    """Helper wrapper that supports float conversion while tracking mutations."""

    def __init__(self, value: float):
        self.value = float(value)

    def __float__(self) -> float:  # pragma: no cover - trivial accessor
        return float(self.value)

    def mutate(self, new_value: float) -> None:
        self.value = float(new_value)

    def __deepcopy__(self, memo):  # pragma: no cover - relied on by deepcopy
        return MutableFloat(self.value)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"MutableFloat({self.value})"


# =============================================================================
# Part 3: Tests for _safe_magnitude, update_bus, and aggregate_alerts
# =============================================================================


# --- 3.1: _safe_magnitude (Helper Function - Bug #82 Fix) ---


class TestSafeMagnitude:
    @pytest.mark.parametrize(
        "value, threshold, expected_magnitude",
        [
            (10, 5, 5.0),
            (5, 10, 5.0),
            (10.5, 5.2, 5.3),
            (-10, -5, 5.0),
            (10, -5, 15.0),
            (0, 0, 0.0),
            (None, 5, 5.0),
            (10, None, 10.0),
            (None, None, 0.0),
            ("10.5", "5.2", 5.3),
        ],
    )
    def test_valid_calculations(self, value, threshold, expected_magnitude):
        """Test standard magnitude calculations with valid numeric inputs."""
        result = _safe_magnitude(value, threshold)
        assert result == pytest.approx(expected_magnitude)

    @pytest.mark.parametrize(
        "value, threshold, expected_error_type",
        [
            ("invalid", 5, "ValueError"),
            (10, "invalid", "ValueError"),
            ("invalid", "invalid", "ValueError"),
            ([1], 5, "TypeError"),
            (10, {"a": 1}, "TypeError"),
        ],
    )
    def test_invalid_inputs(self, value, threshold, expected_error_type, caplog):
        """Test invalid inputs return None and log errors via SafeErrorHandler."""
        logger_name = "optipanel.notify.engine"
        context = "test_ctx"

        with caplog.at_level(logging.ERROR, logger=logger_name):
            result = _safe_magnitude(value, threshold, context=context)
            assert result is None
            assert f"notify.magnitude_calc_failed ({context})" in caplog.text
            assert f"error={expected_error_type}" in caplog.text


# --- 3.2: update_bus (Core Merging Logic) ---


class TestUpdateBus:
    @pytest.fixture
    def bus(self):
        return {}

    def test_input_none_or_empty(self, bus):
        update_bus(bus, None, tick_index=1)
        assert len(bus) == 0
        update_bus(bus, [], tick_index=1)
        assert len(bus) == 0

    def test_input_single_dict(self, bus):
        alert = mock_alert("AAPL", "test")
        update_bus(bus, alert, tick_index=1)
        assert ("AAPL", "test") in bus
        assert bus[("AAPL", "test")]["count"] == 1

    @pytest.mark.parametrize(
        "invalid_input, expected_log_fragment",
        [
            (12345, "expected iterable or mapping, got primitive type 'int'"),
            (True, "expected iterable or mapping, got primitive type 'bool'"),
            ("A STRING ALERT", "expected iterable or mapping, got primitive type 'str'"),
        ],
    )
    def test_input_invalid_type(self, bus, invalid_input, expected_log_fragment, caplog):
        logger_name = "optipanel.notify.engine"
        with caplog.at_level(logging.ERROR, logger=logger_name):
            update_bus(bus, invalid_input, tick_index=1)
        assert len(bus) == 0
        assert expected_log_fragment in caplog.text

    def test_input_list_with_invalid_items(self, bus, caplog):
        alerts = [
            mock_alert("S1", "k1"),
            None,
            "not a mapping",
            mock_alert("S2", "k2"),
        ]
        logger_name = "optipanel.notify.engine"
        with caplog.at_level(logging.WARNING, logger=logger_name):
            update_bus(bus, alerts, tick_index=1)

        assert ("S1", "k1") in bus
        assert ("S2", "k2") in bus
        assert len(bus) == 2

        assert "skipping None alert payload at index 1" in caplog.text
        assert "skipping invalid/failed validation alert payload at index 2" in caplog.text

    def test_initialization_first_alert(self, bus):
        alert = [mock_alert("AAPL", "test", severity="high", message="First", value=10, threshold=5)]
        update_bus(bus, alert, tick_index=100)

        key = ("AAPL", "test")
        assert key in bus
        event = bus[key]

        assert event["count"] == 1
        assert event["first_seen_tick"] == 100
        assert event["last_seen_tick"] == 100
        assert event["severity"] == "high"
        assert event["value"] == 10

    def test_merging_basic_update(self, bus):
        update_bus(bus, [mock_alert("AAPL", "test", message="Msg1")], tick_index=100)
        update_bus(bus, [mock_alert("AAPL", "test", message="Msg2")], tick_index=105)

        event = bus[("AAPL", "test")]
        assert event["count"] == 2
        assert event["last_seen_tick"] == 105
        assert event["message"] == "Msg2"

    def test_message_update_behavior(self, bus):
        key = ("MSG", "test")
        update_bus(bus, [mock_alert("MSG", "test", message="Original")], tick_index=1)

        update_bus(bus, [mock_alert("MSG", "test", message="")], tick_index=2)
        assert bus[key]["message"] == "Original"

        update_bus(bus, [mock_alert("MSG", "test", message=None)], tick_index=3)
        assert bus[key]["message"] == "Original"

        update_bus(bus, [{"symbol": "MSG", "kind": "test"}], tick_index=4)
        assert bus[key]["message"] == "Original"

    def test_merging_severity_ranking(self, bus):
        update_bus(bus, [mock_alert("S1", "k1", severity="low")], tick_index=1)
        assert bus[("S1", "k1")]["severity"] == "low"

        update_bus(bus, [mock_alert("S1", "k1", severity="high")], tick_index=2)
        assert bus[("S1", "k1")]["severity"] == "high"

        update_bus(bus, [mock_alert("S1", "k1", severity="medium")], tick_index=3)
        assert bus[("S1", "k1")]["severity"] == "high"
        assert bus[("S1", "k1")]["count"] == 3

    def test_merging_severity_normalization(self, bus):
        update_bus(bus, [mock_alert("S1", "k1", severity=None)], tick_index=1)
        assert bus[("S1", "k1")]["severity"] == "info"

        update_bus(bus, [mock_alert("S2", "k2", severity="INVALID")], tick_index=2)
        assert bus[("S2", "k2")]["severity"] == "info"

        update_bus(bus, [mock_alert("S1", "k1", severity="MEDIUM")], tick_index=3)
        assert bus[("S1", "k1")]["severity"] == "medium"

    @pytest.mark.parametrize(
        "old_val, old_thresh, new_val, new_thresh, expected_val, expected_thresh",
        [
            (10, 5, 20, 5, 20, 5),
            (20, 5, 10, 5, 20, 5),
            (20, 5, 15, 0, 20, 5),
            (-10, -5, -20, -5, -20, -5),
        ],
    )
    def test_magnitude_comparison(
        self,
        bus,
        old_val,
        old_thresh,
        new_val,
        new_thresh,
        expected_val,
        expected_thresh,
    ):
        update_bus(bus, [mock_alert("M1", "k1", value=old_val, threshold=old_thresh)], tick_index=1)
        update_bus(bus, [mock_alert("M1", "k1", value=new_val, threshold=new_thresh)], tick_index=2)

        event = bus[("M1", "k1")]
        assert event["value"] == expected_val
        assert event["threshold"] == expected_thresh

    def test_magnitude_error_old_invalid_new_valid(self, bus, caplog):
        update_bus(bus, [mock_alert("E1", "k1", value="bad", threshold=5)], tick_index=1)

        update_bus(bus, [mock_alert("E1", "k1", value=10, threshold=5)], tick_index=2)

        event = bus[("E1", "k1")]
        assert event["value"] == 10
        assert event["threshold"] == 5

    def test_magnitude_error_old_valid_new_invalid(self, bus, caplog):
        update_bus(bus, [mock_alert("E1", "k1", value=20, threshold=5)], tick_index=1)

        update_bus(bus, [mock_alert("E1", "k1", value="bad", threshold=5)], tick_index=2)

        event = bus[("E1", "k1")]
        assert event["value"] == 20
        assert event["threshold"] == 5

    def test_magnitude_error_both_invalid(self, bus):
        update_bus(bus, [mock_alert("E1", "k1", value="bad_old", threshold=5)], tick_index=1)
        update_bus(bus, [mock_alert("E1", "k1", value="bad_new", threshold=5)], tick_index=2)

        event = bus[("E1", "k1")]
        assert event.get("value") is None

    def test_alert_event_preserves_raw_and_sanitized_values(self, bus):
        raw_alert = {
            "symbol": "RAW",
            "kind": "dual",
            "severity": "high",
            "value": "not-a-number",
            "threshold": "5",
        }

        update_bus(bus, [raw_alert], tick_index=0)

        event = bus[("RAW", "dual")]
        assert isinstance(event, AlertEvent)
        # Sanitised values are exposed via dict.get
        assert event.get("value") is None
        assert event.get("threshold") == pytest.approx(5)
        # Raw payload remains available for magnitude/logging paths
        assert event.get_raw("value") == "not-a-number"
        assert event.get_raw("threshold") == "5"

        # Updating with valid numerics replaces both sanitised and raw values
        update_bus(bus, [mock_alert("RAW", "dual", value=20, threshold=4)], tick_index=1)
        updated = bus[("RAW", "dual")]
        assert float(updated.get("value")) == pytest.approx(20.0)
        assert float(updated.get("threshold")) == pytest.approx(4.0)
        assert updated.get_raw("value") == 20
        assert updated.get_raw("threshold") == 4

    def test_symbol_normalization_and_raw_storage(self, bus, caplog):
        logger_name = "optipanel.models.alert"
        raw_symbol = "  aapl.nq "
        sanitized_symbol = "AAPL.NQ"
        alert = [mock_alert(raw_symbol, "test")]

        with caplog.at_level(logging.WARNING, logger=logger_name):
            update_bus(bus, alert, tick_index=1)

        key = (sanitized_symbol, "test")
        assert key in bus
        event = bus[key]

        assert event["symbol"] == sanitized_symbol
        assert event["raw_symbol"] == raw_symbol
        assert raw_symbol in caplog.text

    def test_symbol_normalization_merged_capture_on_update(self, bus):
        update_bus(bus, [mock_alert("AAPL", "test")], tick_index=1)
        assert bus[("AAPL", "test")]["raw_symbol"] is None

        raw_symbol = " aapl "
        update_bus(bus, [mock_alert(raw_symbol, "test")], tick_index=2)

        event = bus[("AAPL", "test")]
        assert event["raw_symbol"] == raw_symbol

    def test_symbol_normalization_merged_persistence(self, bus):
        raw_symbol = "TSLA\n"
        update_bus(bus, [mock_alert(raw_symbol, "test")], tick_index=1)
        assert bus[("TSLA", "test")]["raw_symbol"] == raw_symbol

        update_bus(bus, [mock_alert("TSLA", "test")], tick_index=2)
        assert bus[("TSLA", "test")]["raw_symbol"] == raw_symbol

    def test_symbol_normalization_none(self, bus):
        alert = [mock_alert(None, "test")]
        update_bus(bus, alert, tick_index=1)

        expected_symbol = _invalid_symbol_token("missing", "")
        key = (expected_symbol, "test")
        assert key in bus

        event = bus[key]
        assert event["raw_symbol"] == ""

    @pytest.mark.parametrize("field_name", ["sustainment", "supply", "gate", "readiness"])
    def test_deepcopy_prevents_shared_state(self, bus, field_name):
        alert = mock_alert("D1", field_name)

        base_payload = [1, 2]
        alert[field_name] = base_payload

        alert_list = [alert]
        update_bus(bus, alert_list, tick_index=1)

        base_payload.append(3)
        alert_list[0]["symbol"] = "CHANGED"

        event = bus[("D1", field_name)]
        assert event["symbol"] == "D1"

        assert event[field_name] == [1, 2]
        assert event[field_name] is not base_payload

        new_payload = [1000]
        alert_update = mock_alert("D1", field_name)
        alert_update[field_name] = new_payload

        update_bus(bus, [alert_update], tick_index=2)

        new_payload.append(999)
        event = bus[("D1", field_name)]
        assert event[field_name] == [1, 2]
        assert event[field_name] is not new_payload

    def test_optional_fields_capture_and_persistence(self, bus):
        alert1 = mock_alert("OPT", "fields", sustainment={"s1": 1}, supply={"sp1": 1})
        alert2 = mock_alert("OPT", "fields", gate={"g1": 1}, sustainment={"s2": 99}, supply=None)

        update_bus(bus, [alert1], 100)
        key = ("OPT", "fields")
        assert bus[key]["sustainment"] == {"s1": 1}
        assert bus[key]["supply"] == {"sp1": 1}

        update_bus(bus, [alert2], 101)
        assert bus[key]["sustainment"] == {"s1": 1}
        assert bus[key]["supply"] == {"sp1": 1}
        assert bus[key]["gate"] == {"g1": 1}

    def test_tick_index_safety_integration(self, bus, caplog):
        caplog.set_level(logging.WARNING)

        update_bus(bus, [mock_alert("A", "k1")], tick_index="invalid_tick")
        event_a = bus[("A", "k1")]
        assert event_a["first_seen_tick"] == 0
        assert event_a["last_seen_tick"] == 0
        assert "notify.tick_index[A/k1]" in caplog.text

        update_bus(bus, [mock_alert("B", "k1")], tick_index=5)
        update_bus(bus, [mock_alert("B", "k1")], tick_index="another_invalid")
        event_b = bus[("B", "k1")]
        assert event_b["last_seen_tick"] == 5
        assert event_b["count"] == 2
        assert "notify.tick_index[B/k1]" in caplog.text

        bus[("C", "k1")] = {
            "symbol": "C",
            "kind": "k1",
            "severity": "low",
            "count": 1,
            "first_seen_tick": 5,
            "last_seen_tick": "CORRUPT_DATA",
        }
        update_bus(bus, [mock_alert("C", "k1")], tick_index=10)
        event_c = bus[("C", "k1")]
        assert event_c["last_seen_tick"] == 10


class TestAggregateAlerts:
    def test_basic_aggregation(self):
        runs = [
            {
                "alerts": [
                    mock_alert("AAPL", "k1", severity="low", message="M1"),
                    mock_alert("MSFT", "k1", severity="medium"),
                ]
            },
            {
                "alerts": [
                    mock_alert("AAPL", "k1", severity="high", message="M2"),
                    mock_alert("AAPL", "k2", severity="low"),
                ]
            },
        ]

        result = aggregate_alerts(runs)
        events = result["events"]
        counts = result["counts"]

        assert len(events) == 3

        aapl_k1 = next(e for e in events if e["symbol"] == "AAPL" and e["kind"] == "k1")
        assert aapl_k1["count"] == 2
        assert aapl_k1["severity"] == "high"
        assert aapl_k1["message"] == "M2"
        assert aapl_k1["first_seen_tick"] == 0
        assert aapl_k1["last_seen_tick"] == 1

        assert counts == {"high": 1, "medium": 1, "low": 1, "info": 0}

    def test_sorting_complex_scenario(self):
        runs = [
            {
                "alerts": [
                    mock_alert("A", "k1", severity="high", value=10, threshold=0),
                    mock_alert("B", "k1", severity="medium", value=5, threshold=0),
                ]
            },
            {
                "alerts": [
                    mock_alert("C", "k1", severity="high", value=5, threshold=0),
                    mock_alert("D", "k1", severity="medium", value=10, threshold=0),
                ]
            },
            {
                "alerts": [
                    mock_alert("E", "k1", severity="high", value=5, threshold=0),
                    mock_alert("F", "k1", severity="low", value=50, threshold=0),
                ]
            },
        ]

        result = aggregate_alerts(runs)
        symbols = [e["symbol"] for e in result["events"]]
        assert symbols == ["E", "C", "A", "D", "B", "F"]

    def test_sorting_magnitude_errors(self, caplog):
        runs = [
            {
                "alerts": [
                    mock_alert("S_VALID_5", "k1", severity="high", value=5, threshold=0),
                    mock_alert("S_ERROR", "k1", severity="high", value="bad", threshold=0),
                    mock_alert("S_VALID_10", "k1", severity="high", value=10, threshold=0),
                ]
            }
        ]
        result = aggregate_alerts(runs)

        symbols = [e["symbol"] for e in result["events"]]
        assert symbols == ["S_VALID_10", "S_VALID_5", "S_ERROR"]

    def test_sorting_last_seen_tick_safety(self):
        mock_bus_data = {
            ("A", "k1"): {
                "symbol": "A",
                "kind": "k1",
                "severity": "high",
                "last_seen_tick": 10,
                "value": 1,
                "threshold": 0,
            },
            ("B", "k1"): {
                "symbol": "B",
                "kind": "k1",
                "severity": "high",
                "last_seen_tick": "corrupt",
                "value": 1,
                "threshold": 0,
            },
            ("C", "k1"): {
                "symbol": "C",
                "kind": "k1",
                "severity": "high",
                "last_seen_tick": 5,
                "value": 1,
                "threshold": 0,
            },
        }

        def mock_update_bus_side_effect(bus, alerts, tick_index):
            bus.update(deepcopy(mock_bus_data))

        with patch("optipanel.notify.engine.update_bus", side_effect=mock_update_bus_side_effect):
            result = aggregate_alerts([{"alerts": []}])

        symbols = [e["symbol"] for e in result["events"]]
        assert symbols == ["A", "C", "B"]

    def test_use_index_flag_bug80(self):
        runs = [{"alerts": [mock_alert("A", "k1")]}]

        result_list = aggregate_alerts(runs)
        assert isinstance(result_list["events"], list)

        result_index = aggregate_alerts(runs, use_index=True)
        assert isinstance(result_index["events"], AlertIndex)
        assert len(result_index["events"].all_events()) == 1
        assert result_index["events"].by_symbol("A")[0]["symbol"] == "A"

    def test_use_index_sorting_preserved(self):
        runs = [
            {"alerts": [mock_alert("B", "k1", severity="low")]},
            {"alerts": [mock_alert("A", "k1", severity="high")]},
        ]
        result = aggregate_alerts(runs, use_index=True)
        indexed_events = result["events"].all_events()

        assert indexed_events[0]["symbol"] == "A"
        assert indexed_events[1]["symbol"] == "B"

    def test_empty_input(self):
        result_empty = aggregate_alerts([])
        assert result_empty["events"] == []
        assert result_empty["counts"] == {"high": 0, "medium": 0, "low": 0, "info": 0}

        result_none = aggregate_alerts(None)
        assert result_none["events"] == []

    def test_runs_without_alerts_key(self):
        runs = [
            {"tick": 0},
            {"tick": 1, "alerts": [mock_alert("A", "k1")]},
        ]
        result = aggregate_alerts(runs)
        assert len(result["events"]) == 1
        assert result["events"][0]["symbol"] == "A"

    def test_input_data_integrity_bug64(self):
        run1 = {
            "alerts": [
                mock_alert("INTG", "k1", severity="high", value=[1]),
            ]
        }
        run1_copy = deepcopy(run1)

        aggregate_alerts([run1])

        assert run1 == run1_copy
