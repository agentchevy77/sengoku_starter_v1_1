"""Utility helpers for auditing dependency compatibility.

The module inspects the project dependency metadata and highlights packages
that are pinned to incompatible versions across extras/development groups.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


@dataclass(frozen=True)
class RequirementEntry:
    """Represents a requirement declared inside a dependency group."""

    group: str
    requirement: Requirement


@dataclass
class BoundInfo:
    """Lower/upper/exact constraints extracted from a requirement."""

    requirement: Requirement
    exact: set[Version]
    lower: tuple[Version, bool] | None  # (version, inclusive)
    upper: tuple[Version, bool] | None  # (version, inclusive)
    excludes: set[Version]


def load_pyproject(path: Path) -> dict:
    """Load the project metadata from ``pyproject.toml``."""

    with path.open("rb") as handle:
        return tomllib.load(handle)


def gather_requirements(metadata: dict) -> dict[str, list[RequirementEntry]]:
    """Collect all declared requirements grouped by canonical package name."""

    packages: dict[str, list[RequirementEntry]] = {}

    def _add(group: str, values: Iterable[str]) -> None:
        for raw in values:
            req = Requirement(raw)
            name = req.name.lower().replace("_", "-")
            packages.setdefault(name, []).append(RequirementEntry(group, req))

    project = metadata.get("project", {})
    core_deps = project.get("dependencies", [])
    _add("core", core_deps)

    optional = project.get("optional-dependencies", {})
    for group, deps in optional.items():
        _add(group, deps)

    return packages


def _update_lower(current: tuple[Version, bool] | None, version: Version, inclusive: bool) -> tuple[Version, bool]:
    if current is None:
        return version, inclusive
    cur_version, cur_inclusive = current
    if version > cur_version:
        return version, inclusive
    if version == cur_version:
        return version, cur_inclusive and inclusive
    return current


def _update_upper(current: tuple[Version, bool] | None, version: Version, inclusive: bool) -> tuple[Version, bool]:
    if current is None:
        return version, inclusive
    cur_version, cur_inclusive = current
    if version < cur_version:
        return version, inclusive
    if version == cur_version:
        return version, cur_inclusive and inclusive
    return current


def analyze_requirement(entry: RequirementEntry) -> BoundInfo:
    """Extract bound information from a requirement specifier."""

    exact: set[Version] = set()
    excludes: set[Version] = set()
    lower: tuple[Version, bool] | None = None
    upper: tuple[Version, bool] | None = None

    for spec in entry.requirement.specifier:
        op = spec.operator
        version = Version(spec.version)
        if op in {"==", "==="}:
            exact.add(version)
        elif op == "!=":
            excludes.add(version)
        elif op == ">=":
            lower = _update_lower(lower, version, True)
        elif op == ">":
            lower = _update_lower(lower, version, False)
        elif op == "<=":
            upper = _update_upper(upper, version, True)
        elif op == "<":
            upper = _update_upper(upper, version, False)
        elif op == "~=":
            # Compatible release: >=version, and <next major/minor depending on precision
            lower = _update_lower(lower, version, True)
            release = version.release
            next_release = (release[0] + 1,) if len(release) == 1 else release[:-1] + (release[-1] + 1,)
            upper = _update_upper(upper, Version(".".join(map(str, next_release))), False)

    return BoundInfo(entry.requirement, exact, lower, upper, excludes)


def _bounds_conflict(a: BoundInfo, b: BoundInfo) -> bool:
    """Return True when two bounds do not share any valid version."""

    # If either requirement has exact pins, verify compatibility explicitly.
    if a.exact and b.exact:
        return not bool(a.exact & b.exact)

    if a.exact:
        return _exact_conflicts_with_bounds(a.exact, b)
    if b.exact:
        return _exact_conflicts_with_bounds(b.exact, a)

    lower: tuple[Version, bool] | None = None
    upper: tuple[Version, bool] | None = None
    for candidate in (a.lower, b.lower):
        if candidate is not None:
            lower = _update_lower(lower, *candidate)
    for candidate in (a.upper, b.upper):
        if candidate is not None:
            upper = _update_upper(upper, *candidate)

    if lower and upper:
        lower_version, lower_inclusive = lower
        upper_version, upper_inclusive = upper
        if lower_version > upper_version:
            return True
        if lower_version == upper_version and (not lower_inclusive or not upper_inclusive):
            return True
    return False


def _exact_conflicts_with_bounds(exact_versions: Iterable[Version], info: BoundInfo) -> bool:
    for version in exact_versions:
        if version in info.excludes:
            continue
        if info.requirement.specifier:
            if info.requirement.specifier.contains(str(version), prereleases=True):
                return False
        else:
            return False
    return True


def find_conflicts(requirements: dict[str, list[RequirementEntry]]) -> list[dict[str, str]]:
    """Detect conflicting version specifications across dependency groups."""

    issues: list[dict[str, str]] = []

    for name, entries in requirements.items():
        if len(entries) < 2:
            continue
        analyzed = [analyze_requirement(entry) for entry in entries]
        for i in range(len(analyzed)):
            for j in range(i + 1, len(analyzed)):
                if _bounds_conflict(analyzed[i], analyzed[j]):
                    issues.append(
                        {
                            "package": name,
                            "groups": ", ".join(sorted({entries[i].group, entries[j].group})),
                            "req_a": str(entries[i].requirement),
                            "req_b": str(entries[j].requirement),
                        }
                    )
    return issues


def audit_pyproject(path: Path | None = None) -> list[dict[str, str]]:
    """Audit the pyproject dependencies for version compatibility issues."""

    if path is None:
        path = Path(__file__).resolve().parents[2] / "pyproject.toml"

    metadata = load_pyproject(path)
    reqs = gather_requirements(metadata)
    return find_conflicts(reqs)


def main() -> int:
    """CLI entry point returning zero if no issues are found."""

    issues = audit_pyproject()
    if not issues:
        print("No dependency compatibility issues detected.")
        return 0

    print("Dependency compatibility issues detected:\n")
    for issue in issues:
        print(f"- {issue['package']} ({issue['groups']}): {issue['req_a']} vs {issue['req_b']}")
    return 1


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
