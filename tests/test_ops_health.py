from __future__ import annotations

import json
from pathlib import Path

from optipanel.ops.health import collect_health, write_health
from optipanel.runtime.watchdog import WatchdogSnapshot


class DummyFetcher:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.cfg = type("Cfg", (), {"host": "127.0.0.1", "port": 7496, "client_id": 777})()

    def handshake_test(self) -> dict[str, object]:
        if self.ok:
            return {"handshake": "ok", "errors": []}
        raise RuntimeError("boom")


class DummyWatchdog:
    def snapshot(self) -> WatchdogSnapshot:
        return WatchdogSnapshot(
            up=True,
            state="up",
            last_ok_at=123.0,
            last_err_at=None,
            last_error=None,
            interval_sec=5.0,
        )


def test_collect_health_success_includes_watchdog():
    fetcher = DummyFetcher(ok=True)
    payload = collect_health(fetcher, watchdog=DummyWatchdog(), extra={"foo": "bar"})

    assert payload["ok"] is True
    assert payload["handshake"]["handshake"] == "ok"
    assert payload["watchdog"]["state"] == "up"
    assert payload["foo"] == "bar"


def test_collect_health_handles_errors():
    fetcher = DummyFetcher(ok=False)
    payload = collect_health(fetcher)
    assert payload["ok"] is False
    assert payload["errors"] and "RuntimeError" in payload["errors"][0]


def test_write_health(tmp_path: Path):
    data = {"ok": True, "ts": 1.0}
    path = tmp_path / "health" / "tws.json"
    result_path = write_health(path, data)
    assert result_path == path
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == data
