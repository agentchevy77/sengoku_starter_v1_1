from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from optipanel.recon.schemas import validate_recon_entry


@pytest.mark.integration
def test_recon_schema_with_mock_yaml(tmp_path):
    features_yaml = Path(tmp_path) / "features.yaml"
    features_yaml.write_text(
        textwrap.dedent(
            """
            AAA: {last: 105, dma20: 100, support: 101, resistance: 106, rvol: 1.6, rs_strength: 0.3, vwap_diff: 0.01}
            BBB: {last:  95, dma20: 100, support:  96, resistance: 100, rvol: 1.4, rs_strength:-0.2, vwap_diff:-0.01}
            """
        )
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "optipanel.cli.main",
            "recon",
            "--symbols",
            "AAA,BBB",
            "--provider",
            "mock",
            "--features-yaml",
            str(features_yaml),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    for symbol in ("AAA", "BBB"):
        assert symbol in data
        validate_recon_entry(data[symbol])
