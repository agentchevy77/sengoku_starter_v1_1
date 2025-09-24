from __future__ import annotations

import tomllib
from pathlib import Path


def test_expected_optional_extras_present() -> None:
    project_root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = manifest["project"]["optional-dependencies"]

    expected = {
        "async",
        "ui",
        "web",
        "trading",
        "caching",
        "typing",
        "testing",
        "profiling",
        "docs",
        "ibkr",
    }

    assert expected.issubset(extras.keys())


def test_orjson_declared_as_runtime_dependency() -> None:
    project_root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = manifest["project"]["dependencies"]
    assert any(dep.startswith("orjson>=") for dep in dependencies)
