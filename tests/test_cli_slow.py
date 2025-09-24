from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.slow
def test_cli_recon_mock_features(tmp_path: Path) -> None:
    features_path = FIXTURES / "cli_features.yaml"
    assert features_path.exists(), "CLI fixture missing"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "optipanel.cli.main",
            "recon",
            "--provider",
            "mock",
            "--features-yaml",
            str(features_path),
            "--symbols",
            "AAPL,MSFT",
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )

    assert "RECON AAPL" in result.stdout
    assert "RECON MSFT" in result.stdout


@pytest.mark.slow
def test_cli_notify_mock_symbols() -> None:
    payload = {
        "AAPL": {
            "last": 150,
            "dma20": 148,
            "support": 147,
            "resistance": 152,
            "rvol": 1.2,
            "rs_strength": 0.3,
            "vwap_diff": 0.01,
        },
        "MSFT": {
            "last": 410,
            "dma20": 405,
            "support": 400,
            "resistance": 415,
            "rvol": 1.1,
            "rs_strength": 0.2,
            "vwap_diff": -0.02,
        },
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "optipanel.cli.main",
            "notify",
            "--symbols-json",
            json.dumps(payload),
            "--iterations",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )

    assert "events" in result.stdout
    assert "AAPL" in result.stdout
    assert "MSFT" in result.stdout
