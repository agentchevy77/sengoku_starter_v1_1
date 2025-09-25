import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.setup_self_hosted_runner import RunnerConfig, RunnerInstaller


def test_runner_installer_full_flow(tmp_path):
    runner_dir = tmp_path / "runner"

    calls = []

    def fake_runner(cmd, cwd):
        calls.append((tuple(cmd), cwd))

    config = RunnerConfig(
        runner_dir=runner_dir,
        version="2.319.1",
        github_url="https://github.com/ORG/REPO",
        token="token-value",
        labels="ibkr-wheel",
    )

    installer = RunnerInstaller(config, runner=fake_runner)
    installer.run()

    archive = runner_dir / "actions-runner-linux-x64-2.319.1.tar.gz"
    expected_url = (
        "https://github.com/actions/runner/releases/download/"
        "v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz"
    )
    assert calls == [
        (("sudo", "apt", "update"), None),
        (("sudo", "apt", "install", "-y", "git", "unzip", "python3", "python3-venv", "curl"), None),
        (("curl", "-L", "-o", archive.name, expected_url), runner_dir),
        (("tar", "xzf", archive.name), runner_dir),
        (("sudo", "./bin/installdependencies.sh"), runner_dir),
        (("./config.sh", "--url", "https://github.com/ORG/REPO", "--token", "token-value", "--labels", "ibkr-wheel"), runner_dir),
        (("./run.sh",), runner_dir),
    ]


def test_download_skips_when_archive_present(tmp_path, capsys):
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    archive = runner_dir / "actions-runner-linux-x64-2.319.1.tar.gz"
    archive.write_text("cached")

    calls = []

    def fake_runner(cmd, cwd):
        calls.append((tuple(cmd), cwd))

    config = RunnerConfig(
        runner_dir=runner_dir,
        version="2.319.1",
        github_url="https://github.com/org/repo",
        token="token",
        install_prereqs=False,
    )
    installer = RunnerInstaller(config, runner=fake_runner)

    installer.download_runner()
    captured = capsys.readouterr()
    assert "skipping download" in captured.out
    assert calls == []


def test_extract_skips_when_already_present(tmp_path, capsys):
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    archive = runner_dir / "actions-runner-linux-x64-2.319.1.tar.gz"
    archive.write_text("cached")
    (runner_dir / "config.sh").write_text("#!/bin/bash")

    config = RunnerConfig(
        runner_dir=runner_dir,
        version="2.319.1",
        github_url="https://github.com/org/repo",
        token="token",
        install_prereqs=False,
    )

    calls = []

    def fake_runner(cmd, cwd):
        calls.append((tuple(cmd), cwd))

    installer = RunnerInstaller(config, runner=fake_runner)
    installer.extract_runner()
    captured = capsys.readouterr()
    assert "skipping extract" in captured.out
    assert calls == []


def test_config_requires_mandatory_fields(tmp_path):
    runner_dir = tmp_path / "runner"
    with pytest.raises(ValueError):
        RunnerConfig(
            runner_dir=runner_dir,
            version="",
            github_url="https://github.com/org/repo",
            token="token",
        )
    with pytest.raises(ValueError):
        RunnerConfig(
            runner_dir=runner_dir,
            version="2.319.1",
            github_url="",
            token="token",
        )
    with pytest.raises(ValueError):
        RunnerConfig(
            runner_dir=runner_dir,
            version="2.319.1",
            github_url="https://github.com/org/repo",
            token="",
        )
