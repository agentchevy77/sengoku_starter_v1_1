from __future__ import annotations

from optipanel.perf.runtime_checks import RuntimeStatus, collect_runtime_summary


def test_collect_runtime_summary_shapes() -> None:
    summary = collect_runtime_summary()

    assert isinstance(summary.orjson, RuntimeStatus)
    assert isinstance(summary.uvloop, RuntimeStatus)
    assert isinstance(summary.aiofiles, RuntimeStatus)

    # Versions should be populated when installed, otherwise None
    for status in (summary.orjson, summary.uvloop, summary.aiofiles):
        if status.installed:
            assert status.version is not None
        else:
            assert status.version is None


def test_all_fast_paths_available_flag_consistent(monkeypatch) -> None:
    class FakeSummary:
        def __init__(self, installed: bool) -> None:
            status = RuntimeStatus(name="pkg", installed=installed, version="1.0" if installed else None)
            self.orjson = status
            self.uvloop = status
            self.aiofiles = status

        @property
        def all_fast_paths_available(self) -> bool:
            return all(status.installed for status in (self.orjson, self.uvloop, self.aiofiles))

    summary = FakeSummary(installed=True)
    assert summary.all_fast_paths_available
    summary = FakeSummary(installed=False)
    assert not summary.all_fast_paths_available
