from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - skip tests when fastapi missing
    pytest.skip("fastapi not available", allow_module_level=True)  # type: ignore[arg-type]

import importlib
import threading
import time

from optipanel.api.app import AppConfig, app, get_app_config

api_module = importlib.import_module("optipanel.api.app")


def _write_profiles(tmp_path: Path) -> Path:
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        """
watchlists:
  prime: [AAA, BBB]
  secondary: [CCC]
budgets:
  prime: {soft_cap: 10, used_lines: 2}
ui: {width: 20, top_n: 2}
""",
        encoding="utf-8",
    )
    return profiles


def _write_features(tmp_path: Path) -> Path:
    features = tmp_path / "features.yaml"
    features.write_text(
        """
AAA:
  last: 105
  dma20: 100
  support: 102
  resistance: 110
  rvol: 1.4
  rs_strength: 0.2
  vwap_diff: 0.01
BBB:
  last: 95
  dma20: 100
  support: 94
  resistance: 101
  rvol: 1.2
  rs_strength: -0.3
  vwap_diff: -0.02
""",
        encoding="utf-8",
    )
    return features


@contextmanager
def override_config(tmp_path: Path):
    config = AppConfig(
        profiles_path=_write_profiles(tmp_path),
        features_path=_write_features(tmp_path),
        provider="mock",
    )
    app.dependency_overrides[get_app_config] = lambda: config
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_app_config, None)


def test_gather_panels_uses_tick_cache(monkeypatch, tmp_path: Path) -> None:
    api_module._tick_cache.clear()

    profiles_path = _write_profiles(tmp_path)
    features_path = _write_features(tmp_path)

    sample_features = {
        "AAA": {
            "last": 105,
            "dma20": 100,
            "support": 102,
            "resistance": 110,
            "rvol": 1.4,
            "rs_strength": 0.2,
            "vwap_diff": 0.01,
        }
    }

    tick_payload = {
        "run": {
            "ticks": 1,
            "lists": {
                "prime": {
                    "features": sample_features,
                    "budget": {
                        "soft_cap": 10,
                        "cooldown": 0,
                        "scan_stride": 1,
                        "history": [
                            {
                                "tick": 0,
                                "used": 0,
                                "backoff": False,
                                "cooldown_remaining": 0,
                                "scanned": True,
                            }
                        ],
                        "last_used": 0,
                        "backoff": False,
                        "cooldown_remaining": 0,
                    },
                    "panels": [],
                    "advice_counts_last": {},
                    "provider_calls": 1,
                    "scanned_count": 1,
                    "top_last": [],
                    "notify": {"events": [], "counts": {}},
                }
            },
        },
        "panel": "demo",
        "budgets": {
            "prime": {
                "name": "prime",
                "status": "ok",
                "emoji": "🟢",
                "used": 0,
                "soft_cap": 10,
                "backoff": False,
                "cooldown_remaining": 0,
                "scan_stride": 1,
            }
        },
        "watchlists": {"prime": ["AAA"]},
    }

    calls = {"count": 0}

    def fake_run_tick(*_args, **_kwargs):
        calls["count"] += 1
        return tick_payload

    monkeypatch.setattr(api_module, "run_tick", fake_run_tick)

    panels1, ctx1 = api_module.gather_panels(
        provider_name="mock",
        profiles_path=profiles_path,
        features_path=features_path,
        cache_ttl=10.0,
    )
    panels2, ctx2 = api_module.gather_panels(
        provider_name="mock",
        profiles_path=profiles_path,
        features_path=features_path,
        cache_ttl=10.0,
    )

    assert calls["count"] == 1
    assert panels1 and panels2
    assert ctx1["budgets"] == ctx2["budgets"]
    api_module._tick_cache.clear()


def test_tick_cache_single_loader(monkeypatch):
    cache = api_module._TickCache()
    cache.clear()

    call_count = 0
    call_lock = threading.Lock()

    def loader() -> dict[str, int]:
        nonlocal call_count
        with call_lock:
            call_count += 1
        time.sleep(0.05)
        return {"value": call_count}

    results: list[dict[str, int]] = []

    def worker() -> None:
        results.append(cache.get_or_create(("key",), ttl=60.0, loader=loader))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert call_count == 1
    assert all(result == {"value": 1} for result in results)


def test_tick_cache_expires_and_prunes():
    cache = api_module._TickCache()
    cache.clear()

    call_count = {"count": 0}

    def loader() -> dict[str, int]:
        call_count["count"] += 1
        return {"value": call_count["count"]}

    result1 = cache.get_or_create(("key",), ttl=0.1, loader=loader)
    assert result1 == {"value": 1}
    assert call_count["count"] == 1

    time.sleep(0.15)

    result2 = cache.get_or_create(("key",), ttl=0.1, loader=loader)
    assert result2 == {"value": 2}
    assert call_count["count"] == 2


def test_watchlist_endpoint(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/watchlist", params={"top": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["count"] == 1
        assert data["panels"][0]["symbol"] == "AAA"
        assert data["meta"]["budget"]["status"] == "ok"
        assert data["meta"]["budgets"]["prime"]["emoji"] == "🟢"


def test_recon_endpoint_not_found(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/recon/ZZZ")
        assert resp.status_code == 404


def test_recon_endpoint_success(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/recon/AAA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAA"
        assert "battlefield" in body


def test_metrics_endpoint(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["avg_recon"] is not None
        assert body["budgets"]["prime"]["status"] == "ok"


def test_health_endpoint(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
