"""FastAPI application exposing recon/watchlist data."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from optipanel.ui.service import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_PROFILES_PATH,
    PanelSnapshot,
    ProviderConfig,
    budget_status,
    combine_watchlists,
    compute_panel,
    fetch_features,
    load_profiles,
)

app = FastAPI(title="Sengoku Decision Cockpit API", version="0.7.0")


class AppConfig:
    """Container for shared configuration (allows dependency injection)."""

    def __init__(
        self,
        profiles_path: Path = DEFAULT_PROFILES_PATH,
        features_path: Path | None = None,
        provider: str = "mock",
    ) -> None:
        self.profiles_path = profiles_path
        self.features_path = Path(features_path) if features_path else DEFAULT_FEATURES_PATH
        self.provider = provider


def get_app_config() -> AppConfig:
    return AppConfig()


def gather_panels(
    *,
    provider_name: str,
    profiles_path: Path,
    features_path: Path,
    symbols: list[str] | None = None,
    include_supply: bool = True,
) -> tuple[list[PanelSnapshot], dict[str, Any]]:
    profiles = load_profiles(profiles_path)
    watchlist = combine_watchlists(profiles)
    targets = [sym.upper() for sym in symbols if sym] if symbols else watchlist

    provider_cfg = ProviderConfig(name=provider_name, features_path=features_path)
    features = fetch_features(targets, provider=provider_cfg)
    panels = [
        compute_panel(sym, feats, include_supply=include_supply, battlefield_width=profiles.ui_width)
        for sym, feats in features.items()
        if feats
    ]
    panels.sort(key=lambda panel: panel.recon_score, reverse=True)
    return panels, {"profiles": profiles, "watchlist": watchlist}


@app.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/watchlist", summary="Ranked recon entries for the current watchlist")
async def get_watchlist(
    top: int | None = Query(default=None, ge=1, description="Limit to top N symbols"),
    provider: str | None = Query(default=None, description="Feature provider name"),
    config: AppConfig = Depends(get_app_config),  # noqa: B008 - FastAPI dependency injection
) -> JSONResponse:
    panels, ctx = gather_panels(
        provider_name=provider or config.provider,
        profiles_path=config.profiles_path,
        features_path=config.features_path,
    )
    if top is not None:
        panels = panels[:top]

    payload = [serialize_panel(panel) for panel in panels]
    prime_budget = ctx["profiles"].budgets.get("prime") if hasattr(ctx["profiles"], "budgets") else None
    budget = asdict(budget_status("prime", prime_budget)) if prime_budget else None
    meta = {
        "count": len(payload),
        "watchlist": ctx["watchlist"],
        "budget": budget,
    }
    return JSONResponse({"panels": payload, "meta": meta})


@app.get("/recon/{symbol}", summary="Recon detail for a single symbol")
async def get_recon(
    symbol: str,
    provider: str | None = Query(default=None),
    include_supply: bool = Query(default=True),
    config: AppConfig = Depends(get_app_config),  # noqa: B008 - FastAPI dependency injection
) -> JSONResponse:
    panels, _ = gather_panels(
        provider_name=provider or config.provider,
        profiles_path=config.profiles_path,
        features_path=config.features_path,
        symbols=[symbol],
        include_supply=include_supply,
    )
    if not panels:
        raise HTTPException(status_code=404, detail="symbol not found")
    panel = panels[0]
    payload = serialize_panel(panel)
    return JSONResponse(payload)


@app.get("/metrics", summary="Summary metrics (counts, average recon, budget state)")
async def get_metrics(
    provider: str | None = Query(default=None),
    config: AppConfig = Depends(get_app_config),  # noqa: B008 - FastAPI dependency injection
) -> JSONResponse:
    panels, ctx = gather_panels(
        provider_name=provider or config.provider,
        profiles_path=config.profiles_path,
        features_path=config.features_path,
    )
    if not panels:
        return JSONResponse({"count": 0, "avg_recon": None, "budget": None})
    avg_recon = sum(panel.recon_score for panel in panels) / len(panels)
    prime_budget = ctx["profiles"].budgets.get("prime") if hasattr(ctx["profiles"], "budgets") else None
    budget = asdict(budget_status("prime", prime_budget)) if prime_budget else None
    return JSONResponse({"count": len(panels), "avg_recon": avg_recon, "budget": budget})


def serialize_panel(panel: PanelSnapshot) -> dict[str, Any]:
    payload = asdict(panel)
    payload["recon_mode"] = panel.recon.get("mode")
    payload["readiness"] = panel.readiness
    payload["sustainment"] = panel.sustainment
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(prog="python -m optipanel.api.app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--profiles-yaml", default=str(DEFAULT_PROFILES_PATH))
    ap.add_argument("--features-yaml", default=str(DEFAULT_FEATURES_PATH))
    ap.add_argument("--provider", default="mock", choices=["mock", "tws-live"])
    args = ap.parse_args(argv)

    # Bind configuration via dependency override
    def _override() -> AppConfig:
        return AppConfig(
            profiles_path=Path(args.profiles_yaml),
            features_path=Path(args.features_yaml),
            provider=args.provider,
        )

    app.dependency_overrides[get_app_config] = _override
    uvicorn.run("optipanel.api.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
