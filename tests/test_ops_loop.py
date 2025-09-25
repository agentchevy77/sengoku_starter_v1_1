import importlib
import json
from pathlib import Path

from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.ops import ops_loop
from optipanel.ops.ops_loop_enhanced import ops_loop_enhanced, run_watchlist_once_with_logging
from optipanel.ops.session_logger import get_session_logger

ops_module = importlib.import_module("optipanel.ops.ops_loop")


class DummyProvider:
    def __init__(self):
        self.calls = []

    def features_for_symbols(self, symbols):
        self.calls.append(tuple(symbols))
        return {sym: {"last": 100.0, "dma20": 99.0, "support": 95.0, "resistance": 105.0} for sym in symbols}


def test_ops_loop_respects_backoff(monkeypatch):
    provider = DummyProvider()
    profile = {
        "watchlists": {"prime": ["AAPL"], "secondary": ["MSFT"]},
        "budgets": {
            "prime": {"used_lines": [5, 25, 5, 5, 5], "soft_cap": 20, "cooldown": 2, "scan_stride": 1},
            "secondary": {"scan_stride": 2},
        },
    }

    captured = []

    def fake_run_watchlist_once(_provider, symbols, *, width, top_n, logger=None):
        captured.append((tuple(symbols), width, top_n))
        return {"panel": "panel", "run": {}}

    monkeypatch.setattr(ops_module, "run_watchlist_once", fake_run_watchlist_once)

    result = ops_loop(provider, profile, ticks=5, sleep=0, width=24, top_n=2)

    prime_ticks = [entry["tick"] for entry in result["runs"] if entry["list"] == "prime"]
    secondary_ticks = [entry["tick"] for entry in result["runs"] if entry["list"] == "secondary"]

    assert prime_ticks == [0, 4]
    assert secondary_ticks == [0, 2, 4]
    assert captured[0] == (("AAPL",), 24, 2)
    assert captured[1] == (("MSFT",), 24, 2)


BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}
BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 1.5,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
}


def test_ops_runs_prime_and_secondary_without_backoff():
    profile = {
        "watchlists": {"prime": ["AAA", "BBB"], "secondary": ["BBB"]},
        "budgets": {
            "prime": {"soft_cap": 20, "cooldown": 1, "used_lines": [1, 1, 1], "scan_stride": 1},
            "secondary": {"scan_stride": 2},
        },
        "ui": {"width": 24, "top_n": 1},
    }
    provider = MockFeaturesProvider({"AAA": BULL, "BBB": BEAR})
    out = ops_loop(provider, profile, ticks=3, sleep=0, width=24, top_n=1)
    assert out["ticks"] == 3
    assert any("COMMAND ROOM" in r["panel"].upper() for r in out["runs"])
    assert len(out["runs"]) >= 2


class ProviderWithBundles:
    def features_for_symbols(self, symbols):
        base = {
            "last": 101.0,
            "dma20": 100.0,
            "support": 99.0,
            "resistance": 103.0,
            "bundles": {"1d": {"last": 101.0, "support": 99.0, "resistance": 103.0}},
        }
        return dict.fromkeys(symbols, base)


def _load_events(log_dir: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for path in sorted(log_dir.glob("events-*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def test_run_watchlist_once_with_logging_records_operations(monkeypatch, tmp_path):
    monkeypatch.setenv("SENGOKU_LOG_DIR", str(tmp_path))
    provider = ProviderWithBundles()

    with get_session_logger(command="test_watchlist") as logger:
        result = run_watchlist_once_with_logging(
            provider,
            ["AAA"],
            logger,
            width=32,
            top_n=1,
        )

    assert "panel" in result and "run" in result
    events = _load_events(tmp_path)
    kinds = {event.get("kind") for event in events}
    assert "operation" in kinds  # contexts recorded
    assert any(event.get("operation") == "render_panel" for event in events if event.get("kind") == "operation")


def test_ops_loop_enhanced_emits_summary(monkeypatch, tmp_path, capfd):
    monkeypatch.setenv("SENGOKU_LOG_DIR", str(tmp_path))
    provider = ProviderWithBundles()
    profile = {
        "watchlists": {"prime": ["AAA"]},
        "budgets": {"prime": {"used_lines": [5], "soft_cap": 20, "cooldown": 1}},
    }

    result = ops_loop_enhanced(
        provider,
        profile,
        ticks=1,
        sleep=0,
        width=24,
        top_n=1,
    )

    assert result["ticks"] == 1
    assert result["session_id"]
    events = _load_events(tmp_path)
    summary = next(event for event in events if event.get("kind") == "summary")
    assert summary["total_ticks"] == 1
    assert summary["total_runs"] == len(result["runs"])

    # ensure scheduler telemetry recorded
    assert any(event.get("kind") == "scheduler_step" for event in events)
