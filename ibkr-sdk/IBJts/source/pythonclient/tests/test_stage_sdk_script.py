import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.stage_ibkr_sdk import SDKStager, StageConfig


def _create_sdk_archive(tmp_path: Path) -> Path:
    src_root = tmp_path / "src"
    pythonclient = src_root / "IBJts" / "source" / "pythonclient"
    pythonclient.mkdir(parents=True)
    (pythonclient / "README.txt").write_text("hello")

    archive_path = tmp_path / "twsapi.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for file_path in pythonclient.rglob("*"):
            zf.write(file_path, file_path.relative_to(src_root))
    return archive_path


def test_stage_sdk_extracts_structure(tmp_path):
    archive = _create_sdk_archive(tmp_path)
    dest = tmp_path / "dest"
    config = StageConfig(
        archive_path=archive,
        destination=dest,
        owner=None,
        group=None,
        force=False,
        skip_chown=True,
    )
    stager = SDKStager(config)

    pythonclient_path = stager.run()

    expected_file = dest / "IBJts" / "source" / "pythonclient" / "README.txt"
    assert pythonclient_path == expected_file.parent
    assert expected_file.read_text() == "hello"


def test_stage_sdk_requires_force_when_destination_populated(tmp_path):
    archive = _create_sdk_archive(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "existing.txt").write_text("existing")

    config = StageConfig(
        archive_path=archive,
        destination=dest,
        owner=None,
        group=None,
        force=False,
        skip_chown=True,
    )
    stager = SDKStager(config)

    with pytest.raises(FileExistsError):
        stager.run()


def test_stage_sdk_force_clears_destination(tmp_path):
    archive = _create_sdk_archive(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "old.txt").write_text("old")

    config = StageConfig(
        archive_path=archive,
        destination=dest,
        owner=None,
        group=None,
        force=True,
        skip_chown=True,
    )
    stager = SDKStager(config)

    pythonclient_path = stager.run()
    expected_file = dest / "IBJts" / "source" / "pythonclient" / "README.txt"
    assert pythonclient_path == expected_file.parent
    assert not (dest / "old.txt").exists()


def test_apply_ownership_uses_provided_owner(monkeypatch, tmp_path):
    archive = _create_sdk_archive(tmp_path)
    dest = tmp_path / "dest"

    config = StageConfig(
        archive_path=archive,
        destination=dest,
        owner="customuser",
        group="customgroup",
        force=False,
        skip_chown=False,
    )
    stager = SDKStager(config)

    # Prepare destination and extract to populate files for ownership loop.
    stager.prepare_destination()
    stager.extract_archive()

    calls = []

    def fake_getpwnam(name):
        class Pw:
            pw_uid = 123
            pw_name = name
        return Pw()

    def fake_getgrnam(name):
        class Gr:
            gr_gid = 456
            gr_name = name
        return Gr()

    monkeypatch.setattr("scripts.stage_ibkr_sdk.pwd.getpwnam", fake_getpwnam)
    monkeypatch.setattr("scripts.stage_ibkr_sdk.grp.getgrnam", fake_getgrnam)

    def fake_chown(path, uid, gid):
        calls.append((Path(path), uid, gid))

    monkeypatch.setattr("scripts.stage_ibkr_sdk.os.chown", fake_chown)

    stager.apply_ownership()

    assert calls, "expected chown to be invoked"
    for _, uid, gid in calls:
        assert uid == 123
        assert gid == 456


def test_stage_config_requires_archive(tmp_path):
    missing = tmp_path / "missing.zip"
    with pytest.raises(FileNotFoundError):
        StageConfig(
            archive_path=missing,
            destination=tmp_path / "dest",
            owner=None,
            group=None,
            force=False,
            skip_chown=True,
        )
