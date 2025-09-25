from __future__ import annotations

import pytest

from optipanel.cli.main import alerts_main, driver_main, scan_main, snapshot_main


@pytest.mark.parametrize(
    "entrypoint, args, label",
    [
        (snapshot_main, ["--symbol", "AAA", "--features-json", "{"], "features"),
        (scan_main, ["--symbols-json", "{"], "symbols"),
        (alerts_main, ["--symbols-json", "{"], "symbols"),
    ],
)
def test_cli_json_arguments_fail_with_clear_error(entrypoint, args, label, capsys):
    with pytest.raises(SystemExit) as exc_info:
        entrypoint(args)

    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert f"invalid {label} JSON" in err


def test_driver_main_reports_invalid_profile_json(capsys):
    args = [
        "--symbols-json",
        "{}",
        "--profile-json",
        "{",
    ]

    with pytest.raises(SystemExit) as exc_info:
        driver_main(args)

    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "invalid profile JSON" in err
