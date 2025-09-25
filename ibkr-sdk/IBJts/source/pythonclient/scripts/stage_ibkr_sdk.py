#!/usr/bin/env python3
"""Stage the IBKR SDK archive on the self-hosted runner."""
from __future__ import annotations

import argparse
import os
import pwd
import grp
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


@dataclass(frozen=True)
class StageConfig:
    archive_path: Path
    destination: Path
    owner: Optional[str]
    group: Optional[str]
    force: bool
    skip_chown: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "archive_path", self.archive_path.expanduser())
        object.__setattr__(self, "destination", self.destination.expanduser())

        if not self.archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {self.archive_path}")
        if not self.archive_path.is_file():
            raise ValueError(f"Archive path must be a file: {self.archive_path}")

    @property
    def effective_owner(self) -> str:
        return self.owner or pwd.getpwuid(os.getuid()).pw_name

    @property
    def effective_group(self) -> str:
        if self.group:
            return self.group
        try:
            return grp.getgrgid(os.getgid()).gr_name
        except KeyError:
            return pwd.getpwuid(os.getuid()).pw_name


class SDKStager:
    def __init__(self, config: StageConfig) -> None:
        self.config = config

    def prepare_destination(self) -> None:
        dest = self.config.destination
        dest.mkdir(parents=True, exist_ok=True)

        if any(dest.iterdir()) and not self.config.force:
            raise FileExistsError(
                f"Destination {dest} already contains files; use --force to replace."
            )
        if self.config.force:
            for entry in dest.iterdir():
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()

    def extract_archive(self) -> Path:
        dest = self.config.destination
        with zipfile.ZipFile(self.config.archive_path) as archive:
            archive.extractall(dest)

        expected_path = dest / "IBJts" / "source" / "pythonclient"
        if not expected_path.exists():
            raise FileNotFoundError(
                "Expected IBJts/source/pythonclient missing after extraction"
            )
        return expected_path

    def apply_ownership(self) -> None:
        if self.config.skip_chown:
            return
        uid = pwd.getpwnam(self.config.effective_owner).pw_uid
        gid = grp.getgrnam(self.config.effective_group).gr_gid

        for root, dirs, files in os.walk(self.config.destination):
            os.chown(root, uid, gid)
            for name in dirs:
                os.chown(os.path.join(root, name), uid, gid)
            for name in files:
                os.chown(os.path.join(root, name), uid, gid)

    def run(self) -> Path:
        self.prepare_destination()
        path = self.extract_archive()
        self.apply_ownership()
        return path


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archive",
        type=Path,
        help="Path to the IBKR SDK zip archive (e.g., twsapi_macunix.1037.02.zip).",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("/opt/ibkr-sdk"),
        help="Destination directory where the SDK should be staged.",
    )
    parser.add_argument(
        "--owner",
        help="User who should own the staged files (default: current user).",
    )
    parser.add_argument(
        "--group",
        help="Group that should own the staged files (default: current group).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear existing contents in destination before extraction.",
    )
    parser.add_argument(
        "--skip-chown",
        action="store_true",
        help="Skip ownership adjustment (useful when running as root in containers).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv or ())
    try:
        config = StageConfig(
            archive_path=args.archive,
            destination=args.destination,
            owner=args.owner,
            group=args.group,
            force=args.force,
            skip_chown=args.skip_chown,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"[stage] {error}")
        return 1

    stager = SDKStager(config)
    try:
        result_path = stager.run()
    except (FileExistsError, FileNotFoundError) as error:
        print(f"[stage] {error}")
        return 1
    except PermissionError as error:
        print(f"[stage] Permission error: {error}")
        return 1

    print(f"[stage] SDK staged successfully at {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
