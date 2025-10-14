from __future__ import annotations

from typing import Any

RECON_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["recon", "aggregate", "timeframes", "sustainment", "readiness"],
    "properties": {
        "recon": {"type": "integer", "minimum": 0, "maximum": 100},
        "aggregate": {
            "type": "object",
            "additionalProperties": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
        },
        "timeframes": {
            "type": "object",
            "properties": {
                "D": {"type": "object"},
                "H1": {"type": "object"},
                "M15": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "sustainment": {
            "type": "object",
            "required": ["sustainability", "fakeout_risk"],
            "properties": {
                "sustainability": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
                "fakeout_risk": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "additionalProperties": True,
        },
        "supply": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "chips_summary": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
            },
        },
        "readiness": {
            "type": "object",
            "required": ["attack", "defense"],
            "properties": {
                "attack": {"type": "integer", "minimum": 0, "maximum": 100},
                "defense": {"type": "integer", "minimum": 0, "maximum": 100},
                "components": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


def validate_recon_entry(entry: dict[str, Any]) -> None:
    recon = entry.get("recon")
    assert isinstance(recon, int) and 0 <= recon <= 100

    aggregate = entry.get("aggregate")
    if aggregate is None:
        aggregate = entry.get("agg")
    assert isinstance(aggregate, dict)

    timeframes = entry.get("timeframes")
    if timeframes is None:
        timeframes = entry.get("tf")
    assert isinstance(timeframes, dict)

    sustain = entry.get("sustainment")
    assert isinstance(sustain, dict)
    assert isinstance(sustain.get("sustainability"), int)
    assert isinstance(sustain.get("fakeout_risk"), int)

    readiness = entry.get("readiness")
    assert isinstance(readiness, dict)
    assert isinstance(readiness.get("attack"), int)
    assert isinstance(readiness.get("defense"), int)
    assert isinstance(readiness.get("attack"), int)
    assert isinstance(readiness.get("defense"), int)

    supply = entry.get("supply")
    if supply is not None:
        assert isinstance(supply, dict)

    chips_summary = entry.get("chips_summary")
    if chips_summary is not None:
        assert isinstance(chips_summary, dict)
