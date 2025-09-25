#!/usr/bin/env python3
"""Automate the IB API wheel build workflow for Sengoku Decision Cockpit.

This script encapsulates the manual steps documented for reliably producing a
wheel artefact we can redistribute across environments. It performs the
following high-level actions:

1. Ensure a virtual environment exists (optionally recreating it).
2. Upgrade packaging toolchain inside that environment.
3. Build the wheel via ``python -m build``.
4. Sanity check the artefact by installing it and importing ``ibapi``.
5. Copy the resulting wheel to a distribution directory for reuse.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

Command = Sequence[str]
Runner = Callable[[Command, Optional[Path]], None]
CopyFunc = Callable[[Path, Path], Path]
EnvBuilderFactory = Callable[[], venv.EnvBuilder]


@dataclass(frozen=True)
class BuildConfig:
    """Configuration required to drive the build workflow."""

    project_root: Path
    venv_path: Path
    export_dir: Path
    recreate: bool = False
    expected_version: Optional[str] = None

    @property
    def python_executable(self) -> Path:
        """Return the Python executable inside the managed virtualenv."""

        bin_dir = "Scripts" if os.name == "nt" else "bin"
        exe_name = "python.exe" if os.name == "nt" else "python"
        return self.venv_path / bin_dir / exe_name


class WheelBuilder:
    """Coordinates the wheel creation workflow."""

    def __init__(
        self,
        config: BuildConfig,
        runner: Optional[Runner] = None,
        copy_func: Optional[CopyFunc] = None,
        env_builder_factory: Optional[EnvBuilderFactory] = None,
    ) -> None:
        self.config = config
        self.runner = runner or self._run_subprocess
        self.copy_func = copy_func or shutil.copy2
        self.env_builder_factory = env_builder_factory or (
            lambda: venv.EnvBuilder(with_pip=True)
        )

    @staticmethod
    def _run_subprocess(cmd: Command, cwd: Optional[Path] = None) -> None:
        """Execute ``cmd`` with ``subprocess.run`` ensuring failures raise."""

        location = str(cwd) if cwd is not None else os.getcwd()
        print(f"[build] Running: {' '.join(cmd)} (cwd={location})")
        subprocess.run(cmd, check=True, cwd=cwd)

    def ensure_virtualenv(self) -> None:
        """Create the virtualenv if missing or ``recreate`` requested."""

        python_exe = self.config.python_executable
        if self.config.recreate and self.config.venv_path.exists():
            print(f"[build] Removing existing virtualenv at {self.config.venv_path}")
            shutil.rmtree(self.config.venv_path)

        if python_exe.exists():
            print(f"[build] Using existing virtualenv at {self.config.venv_path}")
            return

        print(f"[build] Creating virtualenv at {self.config.venv_path}")
        self.config.venv_path.parent.mkdir(parents=True, exist_ok=True)
        builder = self.env_builder_factory()
        builder.create(str(self.config.venv_path))

    def upgrade_packaging_toolchain(self) -> None:
        """Upgrade pip/setuptools/wheel/build inside the managed environment."""

        python = str(self.config.python_executable)
        cmd = [
            python,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
            "build",
        ]
        self.runner(cmd, None)

    def build_distribution(self) -> None:
        """Invoke ``python -m build`` from the project root."""

        python = str(self.config.python_executable)
        cmd = [python, "-m", "build"]
        self.runner(cmd, self.config.project_root)

    def locate_built_wheel(self) -> Path:
        """Return the most recent ``*.whl`` produced inside ``dist``."""

        dist_dir = self.config.project_root / "dist"
        if not dist_dir.exists():
            raise FileNotFoundError("dist directory not found after build")

        wheels = sorted(
            dist_dir.glob("*.whl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not wheels:
            raise FileNotFoundError("No wheel artefacts were produced")
        return wheels[0]

    def install_wheel(self, wheel_path: Path) -> None:
        """Install the wheel into the build environment for validation."""

        python = str(self.config.python_executable)
        cmd = [python, "-m", "pip", "install", str(wheel_path)]
        self.runner(cmd, None)

    def verify_wheel(self) -> None:
        """Import ``ibapi`` inside the environment to confirm usability."""

        python = str(self.config.python_executable)
        verification_code = (
            'import ibapi; print("ibapi version:", ibapi.__version__)'
        )
        cmd = [python, "-c", verification_code]
        self.runner(cmd, None)

    def validate_expected_version(self, wheel_path: Path) -> None:
        """Ensure the produced wheel matches the requested version."""

        expected = self.config.expected_version
        if not expected:
            return

        try:
            actual = wheel_path.name.split("-")[1]
        except IndexError as exc:
            raise ValueError(f"Unable to determine version from {wheel_path.name}") from exc

        if _normalize_version(expected) != _normalize_version(actual):
            raise ValueError(
                f"Expected wheel version {expected} but produced {wheel_path.name}"
            )

    def export_wheel(self, wheel_path: Path) -> Path:
        """Copy the validated wheel to the export directory."""

        export_dir = self.config.export_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        destination = export_dir / wheel_path.name
        self.copy_func(wheel_path, destination)
        print(f"[build] Exported wheel to {destination}")
        return destination

    def run(self) -> Path:
        """Execute the full build pipeline returning the exported artefact."""

        self.ensure_virtualenv()
        self.upgrade_packaging_toolchain()
        self.build_distribution()
        wheel_path = self.locate_built_wheel()
        self.validate_expected_version(wheel_path)
        self.install_wheel(wheel_path)
        self.verify_wheel()
        return self.export_wheel(wheel_path)


def _default_paths(project_root: Path) -> Tuple[Path, Path]:
    """Derive sensible defaults for the virtualenv and export directories."""

    parents = list(project_root.parents)
    if len(parents) >= 3:
        base_dir = parents[2]
    else:
        base_dir = project_root
    return base_dir / "venv", base_dir / "dist"


def _normalize_version(version: str) -> str:
    """Normalize version segments by stripping leading zeros from numeric parts."""

    normalized_parts = []
    for part in version.split('.'):
        if part.isdigit():
            normalized_parts.append(str(int(part)))
        else:
            normalized_parts.append(part)
    return '.'.join(normalized_parts)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_project_root = Path(__file__).resolve().parent.parent
    default_venv, default_export = _default_paths(default_project_root)

    parser.add_argument(
        "--project-root",
        "--source-dir",
        dest="project_root",
        type=Path,
        default=default_project_root,
        help=f"Path to the pythonclient project (default: {default_project_root})",
    )
    parser.add_argument(
        "--venv-path",
        type=Path,
        default=default_venv,
        help=f"Location for the build virtualenv (default: {default_venv})",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=default_export,
        help=f"Directory where the wheel will be copied (default: {default_export})",
    )
    parser.add_argument(
        "--version",
        dest="expected_version",
        help="Version string the produced wheel filename must contain.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the virtualenv even if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config = BuildConfig(
        project_root=args.project_root,
        venv_path=args.venv_path,
        export_dir=args.export_dir,
        recreate=args.recreate,
        expected_version=args.expected_version,
    )

    builder = WheelBuilder(config)
    try:
        exported_path = builder.run()
    except subprocess.CalledProcessError as error:
        print(f"[build] Command failed: {error}")
        return error.returncode or 1
    except (FileNotFoundError, ValueError) as error:
        print(f"[build] {error}")
        return 1

    print(f"[build] Completed successfully: {exported_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
