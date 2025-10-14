from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from optipanel.perf.latency_probe import LatencyMeasurement, capture_baseline, measure_command


class DummyCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_measure_command_records_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_args: list[Sequence[str]] = []

    def fake_run(cmd: Sequence[str], **_: Any) -> DummyCompleted:
        recorded_args.append(tuple(cmd))
        return DummyCompleted(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = measure_command(["echo", "hello"], timeout=1.0)

    assert isinstance(result, LatencyMeasurement)
    assert recorded_args == [("echo", "hello")]
    assert result.ok
    assert result.stdout == "ok"
    assert result.stderr == ""
    assert result.elapsed_ms >= 0


def test_capture_baseline_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    samples = iter(
        [
            DummyCompleted(0, stdout="run1"),
            DummyCompleted(1, stderr="err"),
        ]
    )

    def fake_run(cmd: Sequence[str], **_: Any) -> DummyCompleted:
        return next(samples)

    monkeypatch.setattr("subprocess.run", fake_run)

    output = tmp_path / "report.json"
    results = capture_baseline([["cmd"]], repeats=2, output=output)

    assert len(results) == 2
    assert output.exists()
    payload = output.read_text(encoding="utf-8")
    assert "cmd" in payload
    assert "ok" in payload
    assert any(not sample.ok for sample in results)
