"""Utilities for auditing installed dependency versions.

The dependency guard is designed to keep the Sengoku toolchain aligned with the
minimum supported versions recorded in ``pyproject.toml``.  It exposes a small
API for programmatic checks and a CLI that can be wired into CI or cron jobs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from importlib import metadata as importlib_metadata
from pathlib import Path

from packaging.version import InvalidVersion, Version


class DependencyState(Enum):
    """Overall health for a dependency."""

    OK = "ok"
    AHEAD = "ahead"
    UPGRADE_REQUIRED = "upgrade_required"
    MISSING = "missing"

    @property
    def is_healthy(self) -> bool:
        """Whether the dependency meets or exceeds the supported baseline."""

        return self in {self.OK, self.AHEAD}


@dataclass(frozen=True)
class DependencyStatus:
    """Summary of the installed version when compared to the required floor."""

    name: str
    required: Version
    installed: Version | None
    state: DependencyState

    @property
    def needs_attention(self) -> bool:
        """True when the dependency is missing or below the supported floor."""

        return not self.state.is_healthy


def _parse_requirement_line(entry: str) -> tuple[str, Version]:
    """Extract a package name and ``>=`` floor from a requirement string.

    ``pyproject.toml`` lists dependencies using ``package>=X.Y`` semantics.  The
    helper keeps the parsing logic contained so that validation can be centralised.
    """

    if ">=" not in entry:
        msg = f"Dependency entry '{entry}' is missing a >= version specifier"
        raise ValueError(msg)
    raw_name, raw_version = entry.split(">=", 1)
    name = raw_name.strip()
    candidate = raw_version.strip()
    try:
        version = Version(candidate)
    except InvalidVersion as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Invalid version '{candidate}' in dependency '{entry}'") from exc
    return name, version


@lru_cache(maxsize=1)
def load_dependency_floors(pyproject_path: Path | None = None) -> tuple[dict[str, Version], dict[str, Version]]:
    """Return runtime and development dependency floors declared in pyproject.

    The values are cached so repeated checks during a run incur minimal cost.
    """

    path = pyproject_path or Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = Path(path).read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - Python <3.11 fallback guard
        raise RuntimeError("Python 3.11+ is required to parse pyproject.toml") from exc

    manifest = tomllib.loads(data)
    project = manifest.get("project", {})
    runtime_entries = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    dev_entries = optional.get("dev", [])

    runtime: MutableMapping[str, Version] = {}
    dev: MutableMapping[str, Version] = {}

    for entry in runtime_entries:
        name, version = _parse_requirement_line(entry)
        runtime[name] = version

    for entry in dev_entries:
        name, version = _parse_requirement_line(entry)
        dev[name] = version

    return dict(runtime), dict(dev)


def inspect_dependency(
    name: str,
    minimum: Version,
    resolver: Callable[[str], str] = importlib_metadata.version,
) -> DependencyStatus:
    """Inspect a single dependency using ``importlib.metadata`` by default."""

    try:
        installed_raw = resolver(name)
    except importlib_metadata.PackageNotFoundError:
        return DependencyStatus(name=name, required=minimum, installed=None, state=DependencyState.MISSING)

    try:
        installed = Version(installed_raw)
    except InvalidVersion:
        # Version parsing failures should be visible without crashing the CLI.
        return DependencyStatus(name=name, required=minimum, installed=None, state=DependencyState.MISSING)

    if installed < minimum:
        state = DependencyState.UPGRADE_REQUIRED
    elif installed == minimum:
        state = DependencyState.OK
    else:
        state = DependencyState.AHEAD

    return DependencyStatus(name=name, required=minimum, installed=installed, state=state)


def collect_statuses(
    requirements: Mapping[str, Version],
    resolver: Callable[[str], str] = importlib_metadata.version,
) -> list[DependencyStatus]:
    """Compute sorted dependency statuses for the provided requirement map."""

    return [inspect_dependency(name, minimum, resolver) for name, minimum in sorted(requirements.items())]


def summarise(statuses: Iterable[DependencyStatus]) -> str:
    """Render a short, human-readable table for CLI output."""

    rows = ["name required installed status"]
    for status in statuses:
        installed = status.installed.public if status.installed else "-"
        rows.append(f"{status.name} {status.required.public} {installed} {status.state.value}")
    return "\n".join(rows)


def evaluate_dependencies(
    include_dev: bool = False,
    resolver: Callable[[str], str] = importlib_metadata.version,
) -> list[DependencyStatus]:
    """Gather statuses for runtime dependencies (and optionally dev tools)."""

    runtime, dev = load_dependency_floors()
    requirements: MutableMapping[str, Version] = dict(runtime)
    if include_dev:
        requirements.update(dev)
    return collect_statuses(requirements, resolver)


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point used by maintenance scripts and CI."""

    import argparse

    parser = argparse.ArgumentParser(description="Audit Sengoku dependency floors against the active environment.")
    parser.add_argument("--include-dev", action="store_true", help="check development dependencies as well")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit with a non-zero status when any dependency is missing or below the floor",
    )
    args = parser.parse_args(argv)

    statuses = evaluate_dependencies(include_dev=args.include_dev)
    print(summarise(statuses))

    if args.strict and any(status.needs_attention for status in statuses):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
