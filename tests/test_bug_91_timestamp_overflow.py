"""Regression tests for Bug #91: timestamp overflow in session logger rotation."""

from __future__ import annotations

import re
from pathlib import Path

from optipanel.ops.session_logger_safe import SafeLogRotationManager


def test_rotate_file_uses_monotonic_ns(tmp_path: Path) -> None:
    """Rotation filenames should include monotonic clock values (nanoseconds)."""

    manager = SafeLogRotationManager(str(tmp_path), max_size_mb=0)
    target = tmp_path / "events.jsonl"
    target.write_text("test\n")

    rotated = manager.rotate_file_safe(target)
    assert rotated is not None
    # Name format includes monotonic ns component followed by PID
    assert re.search(r"\.\d{12,}-\d+", rotated.name), rotated.name
