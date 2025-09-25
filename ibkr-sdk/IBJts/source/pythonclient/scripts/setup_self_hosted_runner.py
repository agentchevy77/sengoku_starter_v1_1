#!/usr/bin/env python3
"""Prepare a GitHub Actions self-hosted runner for IBKR wheel builds."""
from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

Command = Sequence[str]
Runner = Callable[[Command, Optional[Path]], None]

DEFAULT_PACKAGES: Tuple[str, ...] = (
    "git",
    "unzip",
    "python3",
    "python3-venv",
    "curl",
)


@dataclass
class RunnerConfig:
    """Configuration describing how to provision the self-hosted runner."""

    runner_dir: Path
    version: str
    github_url: str
    token: str
    labels: str = "ibkr-wheel"
    archive_url: Optional[str] = None
    install_prereqs: bool = True
    launch: bool = True
    unattended: bool = False
    force_download: bool = False
    use_sudo: bool = True
    packages: Tuple[str, ...] = field(default_factory=lambda: DEFAULT_PACKAGES)

    def __post_init__(self) -> None:
        self.runner_dir = self.runner_dir.expanduser()
        if not self.github_url:
            raise ValueError("GitHub repository or organization URL is required")
        if not self.token:
            raise ValueError("Registration token is required")
        if not self.version:
            raise ValueError("Runner version is required")

    @property
    def archive_filename(self) -> str:
        return f"actions-runner-linux-x64-{self.version}.tar.gz"

    @property
    def resolved_archive_url(self) -> str:
        if self.archive_url:
            return self.archive_url
        return (
            "https://github.com/actions/runner/releases/download/"
            f"v{self.version}/{self.archive_filename}"
        )

    @property
    def archive_path(self) -> Path:
        return self.runner_dir / self.archive_filename


class RunnerInstaller:
    """Implements the provisioning workflow for the self-hosted runner."""

    def __init__(self, config: RunnerConfig, runner: Optional[Runner] = None) -> None:
        self.config = config
        self.runner = runner or self._run_subprocess

    @staticmethod
    def _run_subprocess(cmd: Command, cwd: Optional[Path] = None) -> None:
        location = str(cwd) if cwd else os.getcwd()
        print(f"[runner] Executing: {' '.join(cmd)} (cwd={location})")
        subprocess.run(cmd, check=True, cwd=cwd)

    def install_prerequisites(self) -> None:
        if not self.config.install_prereqs:
            return
        sudo_prefix = ["sudo"] if self.config.use_sudo else []
        self.runner(sudo_prefix + ["apt", "update"], None)
        self.runner(
            sudo_prefix
            + ["apt", "install", "-y", *self.config.packages],
            None,
        )

    def prepare_directory(self) -> None:
        self.config.runner_dir.mkdir(parents=True, exist_ok=True)

    def download_runner(self) -> None:
        if self.config.archive_path.exists() and not self.config.force_download:
            print(
                f"[runner] Archive already present at {self.config.archive_path}, skipping download"
            )
            return
        cmd = [
            "curl",
            "-L",
            "-o",
            str(self.config.archive_path.name),
            self.config.resolved_archive_url,
        ]
        self.runner(cmd, self.config.runner_dir)

    def extract_runner(self) -> None:
        if (self.config.runner_dir / "config.sh").exists() and not self.config.force_download:
            print(
                f"[runner] Runner already extracted at {self.config.runner_dir}, skipping extract"
            )
            return
        cmd = ["tar", "xzf", self.config.archive_path.name]
        self.runner(cmd, self.config.runner_dir)

    def install_runtime_dependencies(self) -> None:
        cmd = ["./bin/installdependencies.sh"]
        sudo_prefix = ["sudo"] if self.config.use_sudo else []
        self.runner(sudo_prefix + cmd, self.config.runner_dir)

    def configure_runner(self) -> None:
        cmd = [
            "./config.sh",
            "--url",
            self.config.github_url,
            "--token",
            self.config.token,
            "--labels",
            self.config.labels,
        ]
        if self.config.unattended:
            cmd.append("--unattended")
        self.runner(cmd, self.config.runner_dir)

    def launch_runner(self) -> None:
        if not self.config.launch:
            print("[runner] Launch step skipped by configuration")
            return
        self.runner(["./run.sh"], self.config.runner_dir)

    def run(self) -> None:
        self.install_prerequisites()
        self.prepare_directory()
        self.download_runner()
        self.extract_runner()
        self.install_runtime_dependencies()
        self.configure_runner()
        self.launch_runner()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runner-dir",
        type=Path,
        default=Path("/opt/github-runner"),
        help="Directory where the runner should be installed.",
    )
    parser.add_argument(
        "--version",
        default="2.319.1",
        help="GitHub Actions runner version (default: 2.319.1)",
    )
    parser.add_argument(
        "--github-url",
        required=True,
        help="Repository or organization URL the runner will attach to.",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Registration token generated from GitHub UI.",
    )
    parser.add_argument(
        "--labels",
        default="ibkr-wheel",
        help="Comma separated labels to register with the runner (default: ibkr-wheel)",
    )
    parser.add_argument(
        "--archive-url",
        help="Override download URL for the runner tarball.",
    )
    parser.add_argument(
        "--no-prereqs",
        action="store_true",
        help="Skip apt-based prerequisite installation.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Do not start the runner after configuration (useful for services).",
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Pass --unattended to config.sh to avoid interactive prompts.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download and re-extract the runner even if files exist.",
    )
    parser.add_argument(
        "--no-sudo",
        action="store_true",
        help="Run commands without sudo (assumes current user has required privileges).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or ())
    config = RunnerConfig(
        runner_dir=args.runner_dir,
        version=args.version,
        github_url=args.github_url,
        token=args.token,
        labels=args.labels,
        archive_url=args.archive_url,
        install_prereqs=not args.no_prereqs,
        launch=not args.no_launch,
        unattended=args.unattended,
        force_download=args.force_download,
        use_sudo=not args.no_sudo,
    )

    installer = RunnerInstaller(config)
    try:
        installer.run()
    except subprocess.CalledProcessError as error:
        print(f"[runner] Command failed: {error}")
        return error.returncode or 1
    except ValueError as error:
        print(f"[runner] {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
