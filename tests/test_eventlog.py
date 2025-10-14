from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from optipanel.ops.eventlog import EventLogger


@pytest.fixture
def fixed_day(monkeypatch) -> str:
    target_struct = time.struct_time((2025, 3, 14, 0, 0, 0, 4, 73, 0))
    monkeypatch.setattr(time, "gmtime", lambda: target_struct)
    return "20250314"


def test_event_logger_writes_daily_file(tmp_path: Path, fixed_day: str) -> None:
    logger = EventLogger(log_dir=str(tmp_path))
    path = logger.emit("watchdog", {"state": "up"})

    assert path == tmp_path / f"events-{fixed_day}.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    first = json.loads(lines[0])
    assert first["kind"] == "watchdog"
    assert first["state"] == "up"
    assert isinstance(first["ts"], float)

    logger.emit("watchdog", {"state": "down"})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_event_logger_uses_env(tmp_path: Path, monkeypatch, fixed_day: str) -> None:
    monkeypatch.setenv("SENGOKU_LOG_DIR", str(tmp_path))
    logger = EventLogger()
    out_path = logger.emit("alert", {"symbol": "AAPL"})
    assert out_path == tmp_path / f"events-{fixed_day}.jsonl"

    body = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
    assert body["symbol"] == "AAPL"
