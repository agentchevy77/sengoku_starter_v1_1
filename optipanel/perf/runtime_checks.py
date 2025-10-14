"""Runtime feature detection for performance-critical dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import NamedTuple


class RuntimeStatus(NamedTuple):
    name: str
    installed: bool
    version: str | None


@dataclass(frozen=True)
class RuntimeSummary:
    orjson: RuntimeStatus
    uvloop: RuntimeStatus
    aiofiles: RuntimeStatus

    @property
    def all_fast_paths_available(self) -> bool:
        return all(status.installed for status in (self.orjson, self.uvloop, self.aiofiles))


def _probe_package(name: str) -> RuntimeStatus:
    try:
        version = metadata.version(name)
    except metadata.PackageNotFoundError:
        return RuntimeStatus(name=name, installed=False, version=None)
    return RuntimeStatus(name=name, installed=True, version=version)


def collect_runtime_summary() -> RuntimeSummary:
    """Return a summary of performance packages present in the environment."""

    return RuntimeSummary(
        orjson=_probe_package("orjson"),
        uvloop=_probe_package("uvloop"),
        aiofiles=_probe_package("aiofiles"),
    )
