from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

try:  # pragma: no cover - optional dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - skip tests when fastapi missing
    pytest.skip("fastapi not available", allow_module_level=True)  # type: ignore[arg-type]

from optipanel.api.app import AppConfig, app, get_app_config


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


def test_watchlist_endpoint(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/watchlist", params={"top": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["count"] == 1
        assert data["panels"][0]["symbol"] == "AAA"
        assert data["meta"]["budget"]["status"] == "ok"


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


def test_health_endpoint(tmp_path: Path) -> None:
    with override_config(tmp_path):
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
