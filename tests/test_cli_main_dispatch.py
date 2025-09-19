import pytest

from optipanel.cli import main as cli_main


@pytest.mark.parametrize(
    "argv, target, expected_args",
    [
        (
            ["snapshot", "--symbol", "AAPL", "--features-json", "{}"],
            "snapshot_main",
            ["--symbol", "AAPL", "--features-json", "{}"],
        ),
        (
            ["scan", "--symbols-json", "{}"],
            "scan_main",
            ["--symbols-json", "{}"],
        ),
        (
            ["alerts", "--symbols-json", "{}"],
            "alerts_main",
            ["--symbols-json", "{}"],
        ),
        (
            ["loop", "--symbols-json", "{}", "--iterations", "5", "--sleep", "1.25"],
            "loop_main",
            ["--symbols-json", "{}", "--iterations", "5", "--sleep", "1.25"],
        ),
        (
            [
                "command-room",
                "--symbols-json",
                "{}",
                "--width",
                "40",
                "--top-n",
                "3",
                "--iterations",
                "2",
                "--sleep",
                "0.5",
            ],
            "command_room_main",
            [
                "--symbols-json",
                "{}",
                "--width",
                "40",
                "--top-n",
                "3",
                "--iterations",
                "2",
                "--sleep",
                "0.5",
            ],
        ),
        (
            [
                "driver",
                "--symbols-json",
                "{}",
                "--profile-json",
                '{"tick":1}',
                "--ticks",
                "4",
                "--sleep",
                "0.1",
            ],
            "driver_main",
            [
                "--symbols-json",
                "{}",
                "--profile-json",
                '{"tick":1}',
                "--ticks",
                "4",
                "--sleep",
                "0.1",
            ],
        ),
        (
            [
                "profiles",
                "--profiles-yaml",
                "profiles.yml",
                "--features-yaml",
                "features.yml",
                "--ticks",
                "7",
            ],
            "profiles_main",
            [
                "--profiles-yaml",
                "profiles.yml",
                "--features-yaml",
                "features.yml",
                "--ticks",
                "7",
            ],
        ),
        (
            ["notify", "--symbols-json", "{}", "--iterations", "9"],
            "notify_main",
            ["--symbols-json", "{}", "--iterations", "9"],
        ),
        (
            [
                "profiles-live",
                "--profiles-yaml",
                "profiles.yml",
                "--provider",
                "mock",
                "--ticks",
                "5",
            ],
            "profiles_live_main",
            [
                "--profiles-yaml",
                "profiles.yml",
                "--provider",
                "mock",
                "--features-yaml",
                "",
                "--ticks",
                "5",
            ],
        ),
    ],
)
def test_main_dispatches_to_subcommand(monkeypatch, argv, target, expected_args):
    called = {}

    def make_stub(name):
        def _stub(received=None):
            called[name] = list(received or [])
            return 0

        return _stub

    # Patch all known entrypoints to guard against accidental invocation.
    for attr in (
        "snapshot_main",
        "scan_main",
        "alerts_main",
        "loop_main",
        "command_room_main",
        "driver_main",
        "profiles_main",
        "notify_main",
        "profiles_live_main",
    ):
        monkeypatch.setattr(cli_main, attr, make_stub(attr))

    result = cli_main.main(argv)

    assert result == 0
    assert called[target] == expected_args
    # Ensure only the targeted handler was invoked
    assert len([name for name, args in called.items() if args]) == 1


def test_profiles_live_forwards_feature_path(monkeypatch):
    captured = {}

    def stub(args=None):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli_main, "profiles_live_main", stub)
    argv = [
        "profiles-live",
        "--profiles-yaml",
        "profiles.yml",
        "--provider",
        "tws-live",
        "--features-yaml",
        "feats.yml",
        "--ticks",
        "2",
    ]
    cli_main.main(argv)
    assert captured["args"] == [
        "--profiles-yaml",
        "profiles.yml",
        "--provider",
        "tws-live",
        "--features-yaml",
        "feats.yml",
        "--ticks",
        "2",
    ]
