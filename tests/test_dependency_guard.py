from importlib import metadata as importlib_metadata

import pytest
from packaging.version import Version

from optipanel.ops import dependency_guard
from optipanel.ops.dependency_guard import (
    DependencyState,
    DependencyStatus,
    collect_statuses,
    inspect_dependency,
    summarise,
)


def test_inspect_dependency_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> str:
        raise importlib_metadata.PackageNotFoundError

    status = inspect_dependency("pyyaml", Version("6.0.2"), resolver=_raise)
    assert status.state is DependencyState.MISSING
    assert status.installed is None


def test_inspect_dependency_upgrade_required() -> None:
    def _resolver(_: str) -> str:
        return "5.0.0"

    status = inspect_dependency("pyyaml", Version("6.0.2"), resolver=_resolver)
    assert status.state is DependencyState.UPGRADE_REQUIRED
    assert status.installed == Version("5.0.0")


def test_inspect_dependency_equal_floor() -> None:
    def _resolver(_: str) -> str:
        return "6.0.2"

    status = inspect_dependency("pyyaml", Version("6.0.2"), resolver=_resolver)
    assert status.state is DependencyState.OK
    assert status.installed == Version("6.0.2")


def test_inspect_dependency_ahead() -> None:
    def _resolver(_: str) -> str:
        return "6.1.0"

    status = inspect_dependency("pyyaml", Version("6.0.2"), resolver=_resolver)
    assert status.state is DependencyState.AHEAD
    assert status.installed == Version("6.1.0")


def test_collect_statuses_sorted() -> None:
    requirements = {"b": Version("1.0"), "a": Version("1.0")}

    def _resolver(name: str) -> str:
        return {"a": "1.1", "b": "1.0"}[name]

    statuses = collect_statuses(requirements, resolver=_resolver)
    assert [status.name for status in statuses] == ["a", "b"]


def test_summarise_formats_table() -> None:
    statuses = [
        DependencyStatus(name="alpha", required=Version("1.0"), installed=Version("1.2"), state=DependencyState.AHEAD),
        DependencyStatus(name="beta", required=Version("2.0"), installed=None, state=DependencyState.MISSING),
    ]
    output = summarise(statuses)
    assert "alpha" in output
    assert "beta" in output
    assert output.count("\n") == 2


def test_evaluate_dependencies_aggregates_runtime_and_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_load() -> tuple[dict[str, Version], dict[str, Version]]:
        return {"runtime-one": Version("1.0")}, {"dev-one": Version("2.0")}

    def _resolver(name: str) -> str:
        return {"runtime-one": "1.1", "dev-one": "2.0"}[name]

    monkeypatch.setattr(dependency_guard, "load_dependency_floors", _fake_load)

    statuses = dependency_guard.evaluate_dependencies(include_dev=True, resolver=_resolver)
    assert {status.name for status in statuses} == {"runtime-one", "dev-one"}

    dev_only = dependency_guard.evaluate_dependencies(include_dev=False, resolver=_resolver)
    assert {status.name for status in dev_only} == {"runtime-one"}
