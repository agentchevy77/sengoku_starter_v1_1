"""FastAPI application exposing recon/watchlist data."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event, RLock
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
    run_tick,
)

app = FastAPI(title="Sengoku Decision Cockpit API", version="0.7.0")


@dataclass
class AppConfig:
    """Container for shared configuration (allows dependency injection)."""

    profiles_path: Path = DEFAULT_PROFILES_PATH
    features_path: Path | None = None
    provider: str = "mock"
    cache_ttl: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.profiles_path, Path):
            self.profiles_path = Path(self.profiles_path)
        if self.features_path is None:
            self.features_path = DEFAULT_FEATURES_PATH
        elif not isinstance(self.features_path, Path):
            self.features_path = Path(self.features_path)
        self.cache_ttl = max(0.0, float(self.cache_ttl))


@dataclass
class _TickCacheEntry:
    expires_at: float
    payload: dict[str, Any]


class _TickCache:
    """Simple in-memory cache so concurrent API calls reuse the latest tick."""

    def __init__(self) -> None:
        self._data: dict[tuple[Any, ...], _TickCacheEntry] = {}
        self._lock = RLock()
        self._inflight: dict[tuple[Any, ...], Event] = {}
        self._last_prune = 0.0
        self._prune_interval = 60.0  # Prune at most once per minute

    def _prune_expired(self, now: float) -> None:
        """Prune expired entries efficiently and thread-safely.

        This method must be called while holding self._lock to ensure thread safety.
        It iterates over a copy of items to prevent race conditions during pruning.
        """
        # Thread-safe iteration: list() creates a snapshot copy of items
        # This prevents RuntimeError: dictionary changed size during iteration
        # Note: This method assumes it's called while holding self._lock
        for k, v in list(self._data.items()):
            if v.expires_at <= now:
                self._data.pop(k, None)

    def get_or_create(
        self,
        key: tuple[Any, ...],
        ttl: float,
        loader: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if ttl <= 0:
            return loader()

        while True:
            with self._lock:
                now = time.time()
                # Only prune periodically to avoid performance hit
                if now - self._last_prune > self._prune_interval:
                    self._prune_expired(now)
                    self._last_prune = now

                entry = self._data.get(key)
                if entry and entry.expires_at > now:
                    return entry.payload
                if entry and entry.expires_at <= now:
                    self._data.pop(key, None)

                waiter = self._inflight.get(key)
                if waiter is None:
                    waiter = Event()
                    self._inflight[key] = waiter
                    break

            # Another thread is populating this key; wait for it with timeout
            # If timeout expires, we'll retry the loop and either find data or become the loader
            if not waiter.wait(timeout=30.0):
                # Remove stale waiter to prevent zombie events
                with self._lock:
                    current_waiter = self._inflight.get(key)
                    if current_waiter is waiter:
                        self._inflight.pop(key, None)
                # Log warning and continue loop to retry
                import logging

                logging.warning(f"Cache wait timeout for key {key[:2] if key else 'unknown'}...")

        try:
            payload = loader()
        except Exception:
            with self._lock:
                self._data.pop(key, None)
                event = self._inflight.pop(key, None)
                if event is not None:
                    event.set()
            raise

        with self._lock:
            now = time.time()
            expires_at = now + ttl
            self._data[key] = _TickCacheEntry(expires_at=expires_at, payload=payload)
            # Use same time value to avoid immediate expiration bug
            if now - self._last_prune > self._prune_interval:
                self._prune_expired(now)
                self._last_prune = now
            event = self._inflight.pop(key, None)
            if event is not None:
                event.set()
        return payload

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            for event in self._inflight.values():
                event.set()
            self._inflight.clear()


_tick_cache = _TickCache()


def get_app_config() -> AppConfig:
    return AppConfig()


def gather_panels(
    *,
    provider_name: str,
    profiles_path: Path,
    features_path: Path,
    symbols: list[str] | None = None,
    include_supply: bool = True,
    cache_ttl: float = 0.0,
) -> tuple[list[PanelSnapshot], dict[str, Any]]:
    profiles = load_profiles(profiles_path)
    watchlist = combine_watchlists(profiles)
    key = (
        str(profiles_path),
        provider_name,
        str(features_path),
        profiles.ui_width,
        profiles.top_n,
    )

    def _loader() -> dict[str, Any]:
        return run_tick(
            profiles_path,
            provider_name,
            features_yaml_path=features_path,
            width=profiles.ui_width,
            top_n=profiles.top_n,
        )

    tick = _tick_cache.get_or_create(key, cache_ttl, _loader)
    run_out = tick.get("run", {}) if isinstance(tick, dict) else {}
    lists = run_out.get("lists", {}) if isinstance(run_out, dict) else {}

    features: dict[str, dict[str, Any]] = {}
    for details in lists.values():
        if not isinstance(details, dict):
            continue
        payload = details.get("features")
        if isinstance(payload, dict):
            for sym, feats in payload.items():
                # Performance: Only copy if we're keeping it
                if not (isinstance(feats, dict) and feats.get("last")):
                    continue
                sym_upper = str(sym).upper()  # Compute once
                features[sym_upper] = dict(feats)  # Copy only if needed

    targets = [sym.upper() for sym in symbols if sym] if symbols else watchlist
    missing = [sym for sym in targets if sym not in features]
    if missing:
        provider_cfg = ProviderConfig(name=provider_name, features_path=features_path)
        extra = fetch_features(missing, provider=provider_cfg)
        for sym, feats in extra.items():
            # Performance optimization: same pattern as above
            if not (isinstance(feats, dict) and feats.get("last")):
                continue
            features[str(sym).upper()] = dict(feats)

    panels = [
        compute_panel(sym, feats, include_supply=include_supply, battlefield_width=profiles.ui_width)
        for sym, feats in features.items()
        if feats and sym in targets
    ]
    # Safe sort with None handling - None values sort to bottom (treated as -infinity)
    panels.sort(key=lambda panel: panel.recon_score if panel.recon_score is not None else float("-inf"), reverse=True)
    raw_budgets = tick.get("budgets", {}) if isinstance(tick, dict) else {}
    budgets: dict[str, Any] = dict(raw_budgets) if isinstance(raw_budgets, dict) else {}
    if "prime" not in budgets:
        prime_cfg = profiles.budgets.get("prime") if hasattr(profiles, "budgets") else None
        budgets["prime"] = asdict(budget_status("prime", prime_cfg))

    meta = {
        "profiles": profiles,
        "watchlist": watchlist,
        "budgets": budgets,
        "runtime": run_out,
    }
    return panels, meta


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
        cache_ttl=config.cache_ttl,
    )
    if top is not None:
        panels = panels[:top]

    payload = [serialize_panel(panel) for panel in panels]
    budgets = ctx.get("budgets", {}) if isinstance(ctx, dict) else {}
    budget = budgets.get("prime")
    meta = {
        "count": len(payload),
        "watchlist": ctx["watchlist"],
        "budget": budget,
        "budgets": budgets,
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
        cache_ttl=config.cache_ttl,
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
        cache_ttl=config.cache_ttl,
    )
    if not panels:
        return JSONResponse({"count": 0, "avg_recon": None, "budget": None, "budgets": {}})
    # Safe calculation with None filtering
    valid_scores = [panel.recon_score for panel in panels if panel.recon_score is not None]
    avg_recon = sum(valid_scores) / len(valid_scores) if valid_scores else None
    budgets = ctx.get("budgets", {}) if isinstance(ctx, dict) else {}
    budget = budgets.get("prime")
    return JSONResponse({"count": len(panels), "avg_recon": avg_recon, "budget": budget, "budgets": budgets})


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
    ap.add_argument("--cache-ttl", type=float, default=0.0, help="Seconds to cache the latest tick (0 disables cache)")
    args = ap.parse_args(argv)

    # Bind configuration via dependency override
    def _override() -> AppConfig:
        return AppConfig(
            profiles_path=Path(args.profiles_yaml),
            features_path=Path(args.features_yaml),
            provider=args.provider,
            cache_ttl=max(0.0, float(args.cache_ttl)),
        )

    app.dependency_overrides[get_app_config] = _override
    uvicorn.run("optipanel.api.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
