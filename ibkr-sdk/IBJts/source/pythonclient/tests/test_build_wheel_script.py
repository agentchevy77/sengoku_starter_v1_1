import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_wheel import BuildConfig, WheelBuilder, _default_paths


class DummyBuilder:
    def __init__(self) -> None:
        self.created_at = None

    def create(self, path: str) -> None:  # pragma: no cover - not triggered when venv exists
        self.created_at = Path(path)


def test_wheel_builder_executes_full_pipeline(tmp_path):
    project_root = tmp_path / "pythonclient"
    project_root.mkdir()
    dist_dir = project_root / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "ibapi-10.37.02-py3-none-any.whl"
    wheel_path.write_text("dummy wheel")

    venv_path = tmp_path / "venv"
    python_bin = venv_path / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("#!/usr/bin/env python3\n")

    calls = []

    def fake_runner(cmd, cwd):
        calls.append((tuple(cmd), cwd))

    copied = {}

    def fake_copy(src, dst):
        copied["src"] = Path(src)
        copied["dst"] = Path(dst)
        return dst

    config = BuildConfig(
        project_root=project_root,
        venv_path=venv_path,
        export_dir=tmp_path / "export",
        expected_version="10.37.02",
    )
    builder = WheelBuilder(
        config,
        runner=fake_runner,
        copy_func=fake_copy,
        env_builder_factory=DummyBuilder,
    )

    exported_path = builder.run()

    expected_python = str(python_bin)
    assert calls == [
        ((expected_python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "build"), None),
        ((expected_python, "-m", "build"), project_root),
        ((expected_python, "-m", "pip", "install", str(wheel_path)), None),
        ((expected_python, "-c", 'import ibapi; print("ibapi version:", ibapi.__version__)'), None),
    ]
    assert copied["src"] == wheel_path
    assert copied["dst"] == exported_path == (tmp_path / "export" / wheel_path.name)


def test_locate_built_wheel_requires_artifact(tmp_path):
    project_root = tmp_path / "client"
    project_root.mkdir()
    # No dist directory yet -> error expected
    config = BuildConfig(
        project_root=project_root,
        venv_path=tmp_path / "venv",
        export_dir=tmp_path / "export",
    )
    builder = WheelBuilder(config)

    with pytest.raises(FileNotFoundError):
        builder.locate_built_wheel()

    dist_dir = project_root / "dist"
    dist_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        builder.locate_built_wheel()


def test_default_paths_align_with_repo_structure(tmp_path):
    project_root = tmp_path / "IBJts" / "source" / "pythonclient"
    project_root.mkdir(parents=True)

    venv_path, export_path = _default_paths(project_root)
    assert venv_path == project_root.parents[2] / "venv"
    assert export_path == project_root.parents[2] / "dist"


def test_validate_expected_version_mismatch(tmp_path):
    project_root = tmp_path / "pythonclient"
    project_root.mkdir()
    dist_dir = project_root / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "ibapi-10.36.00-py3-none-any.whl"
    wheel_path.write_text("dummy wheel")

    venv_path = tmp_path / "venv"
    python_bin = venv_path / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("#!/usr/bin/env python3\n")

    config = BuildConfig(
        project_root=project_root,
        venv_path=venv_path,
        export_dir=tmp_path / "export",
        expected_version="10.37.02",
    )
    builder = WheelBuilder(
        config,
        runner=lambda *args, **kwargs: None,
        copy_func=lambda src, dst: dst,
        env_builder_factory=DummyBuilder,
    )

    with pytest.raises(ValueError):
        builder.run()
