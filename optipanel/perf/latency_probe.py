"""Latency measurement utilities for Sengoku CLI commands.

The helpers focus on reproducibility: every measurement records the command,
number of runs, wall-clock timing, and success state so we can store baselines
and compare against future Textual/FastAPI prototypes.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class LatencyMeasurement:
    """One measurement sample for a command invocation."""

    command: Sequence[str]
    elapsed_ms: float
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def measure_command(command: Sequence[str], *, timeout: float | None = None) -> LatencyMeasurement:
    """Execute ``command`` and return a structured measurement."""

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - defensive guard
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        stdout = exc.stdout
        if isinstance(stdout, bytes):
            stdout_text = stdout.decode("utf-8", errors="replace")
        elif isinstance(stdout, str):
            stdout_text = stdout
        else:
            stdout_text = ""
        stderr_text = f"timeout: {exc}"
        return LatencyMeasurement(
            command=tuple(command),
            elapsed_ms=elapsed_ms,
            returncode=-1,
            stdout=stdout_text,
            stderr=stderr_text,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return LatencyMeasurement(
        command=tuple(command),
        elapsed_ms=elapsed_ms,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def capture_baseline(
    commands: Iterable[Sequence[str]],
    *,
    repeats: int = 3,
    output: str | Path | None = None,
    timeout: float | None = None,
) -> list[LatencyMeasurement]:
    """Measure each command ``repeats`` times and optionally persist JSON."""

    results: list[LatencyMeasurement] = []
    for _ in range(repeats):
        for command in commands:
            results.append(measure_command(command, timeout=timeout))

    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(sample) | {"ok": sample.ok} for sample in results]
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return results
