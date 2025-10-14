from __future__ import annotations

import json
import time
from pathlib import Path

from optipanel.chips.aggregate import aggregate_chips, recon_score
from optipanel.obs import metrics


def test_metrics_record_and_timer(tmp_path: Path) -> None:
    metrics.reset()

    metrics.record("foo")
    with metrics.timer("bar"):
        time.sleep(0.001)

    snap = metrics.snapshot()
    assert snap["counters"]["foo"] == 1
    assert snap["timers"]["bar"]["count"] == 1
    assert snap["timers"]["bar"]["total_ms"] >= 0.0

    out_path = metrics.export_json(tmp_path / "metrics.json")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == snap


def test_aggregate_and_recon_instrumentation() -> None:
    metrics.reset()

    chips = {
        "D": {"breakout_up": 60, "trend_long": 70, "rejection_down": 20},
        "H1": {"breakout_up": 40, "trend_long": 50, "rejection_down": 30},
    }

    agg = aggregate_chips(chips)
    score = recon_score(agg)

    snap = metrics.snapshot()
    assert snap["counters"]["chips.aggregate.calls"] == 1
    assert snap["counters"]["recon.score.calls"] == 1
    assert snap["timers"]["chips.aggregate.ms"]["count"] == 1
    assert snap["timers"]["recon.score.ms"]["count"] == 1
    assert isinstance(score, int)
