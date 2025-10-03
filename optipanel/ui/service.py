"""Shared helpers for UI surfaces (Textual, web, etc.)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationFileError(Exception):
    """Raised when a configuration file cannot be read due to I/O errors.

    This exception wraps underlying OSError types (PermissionError, FileNotFoundError,
    etc.) to provide actionable context for configuration loading failures.
    """


from optipanel.acceptance.engine import detect_breakout_acceptance
from optipanel.battlefield.ascii import render_battlefield
from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.recon.enrich import build_recon_entry
from optipanel.runtime.profiles_live import run_profiles_with_provider
from optipanel.ui.command_room import render_command_room

try:  # Optional dependency (ibapi) is only required for live provider usage
    from optipanel.adapters.ibkr import RealTwsFetcher, RealTwsFetcherConfig, cfg_from_env
    from optipanel.adapters.ibkr.mock_provider import MockFeaturesProvider
    from optipanel.adapters.ibkr.provider import TwsFeaturesProvider
    from optipanel.adapters.ibkr.translator import translate_snapshots
except Exception:  # pragma: no cover - exercised only when ibapi is absent
    RealTwsFetcher = None  # type: ignore[misc, assignment]
    RealTwsFetcherConfig = None  # type: ignore[misc, assignment]
    cfg_from_env = None  # type: ignore[assignment]
    TwsFeaturesProvider = None  # type: ignore[misc, assignment]
    translate_snapshots = None  # type: ignore[assignment]
    MockFeaturesProvider = None  # type: ignore[misc, assignment]


DEFAULT_PROFILES_PATH = Path("config/examples/live_profiles.yaml")
DEFAULT_FEATURES_PATH = Path("config/examples/features.yaml")

_PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    "tws-live": ("tws-live", "live", "ibkr-live"),
    "mock": ("mock", "tws-mock"),
}


@dataclass(frozen=True)
class Profiles:
    """Parsed watchlist configuration for the UI."""

    prime: list[str]
    secondary: list[str]
    budgets: dict[str, dict[str, Any]]
    ui_width: int
    top_n: int


@dataclass(frozen=True)
class PanelSnapshot:
    """Structured panel data for a single symbol."""

    symbol: str
    recon_score: int
    recon: Mapping[str, Any]
    readiness: Mapping[str, Any]
    sustainment: Mapping[str, Any]
    supply: Mapping[str, Any] | None
    acceptance: Mapping[str, Any]
    battlefield: str
    advice: str
    setups: Mapping[str, int]
    prob_summary: Mapping[str, Any]


@dataclass(frozen=True)
class BudgetStatus:
    """Simple interpretation of budget/backoff state for display."""

    name: str
    status: str
    emoji: str
    used: float
    soft_cap: float


def _ensure_path(path: str | Path | None, default: Path) -> Path:
    if path is None:
        return default
    return Path(path)


def _read_text(path: str | Path) -> str:
    """Read text from a configuration file with comprehensive error handling.

    Args:
        path: Path to the configuration file (string or Path object)

    Returns:
        The file contents as a UTF-8 string

    Raises:
        ConfigurationFileError: When the file cannot be read due to:
            - PermissionError: Insufficient permissions to read the file
            - FileNotFoundError: File does not exist at the specified path
            - IsADirectoryError: Path points to a directory, not a file
            - OSError: Other I/O errors (disk errors, encoding issues, etc.)

    The original exception is preserved in the exception chain for debugging.
    """
    file_path = Path(path)
    abs_path = file_path.resolve()

    try:
        return file_path.read_text(encoding="utf-8")
    except PermissionError as e:
        msg = (
            f"Permission denied when reading configuration file: {abs_path}\n"
            f"Check that the file has read permissions for the current user."
        )
        raise ConfigurationFileError(msg) from e
    except FileNotFoundError as e:
        msg = f"Configuration file not found: {abs_path}\n" f"Verify the file path is correct and the file exists."
        raise ConfigurationFileError(msg) from e
    except IsADirectoryError as e:
        msg = (
            f"Expected a file but found a directory: {abs_path}\n"
            f"Ensure the path points to a configuration file, not a directory."
        )
        raise ConfigurationFileError(msg) from e
    except OSError as e:
        msg = f"Failed to read configuration file: {abs_path}\n" f"I/O error occurred: {e}"
        raise ConfigurationFileError(msg) from e


def _canonical_provider(name: str) -> str:
    alias = (name or "").strip().lower()
    for canonical, aliases in _PROVIDER_ALIASES.items():
        if alias in aliases:
            return canonical
    raise ValueError(f"Unsupported provider: {name}")


def load_profiles(profiles_path: str | Path | None = None) -> Profiles:
    """Read the watchlist profile configuration used by the UI."""

    path = _ensure_path(profiles_path, DEFAULT_PROFILES_PATH)
    text = _read_text(path)
    parsed = parse_profiles_yaml(text)
    watchlists = parsed.get("watchlists", {})
    prime = [str(sym).upper() for sym in watchlists.get("prime", [])]
    secondary = [str(sym).upper() for sym in watchlists.get("secondary", [])]
    budgets = {str(k): dict(v) for k, v in (parsed.get("budgets") or {}).items()}
    ui_cfg = parsed.get("ui") or {}
    width = int(ui_cfg.get("width", 24))
    top_n = int(ui_cfg.get("top_n", max(1, len(prime))))
    return Profiles(prime=prime, secondary=secondary, budgets=budgets, ui_width=width, top_n=top_n)


@dataclass(frozen=True)
class ProviderConfig:
    """Runtime configuration for the feature provider."""

    name: str = "mock"
    features_path: str | Path | None = None
    tws_host: str | None = None
    tws_port: int | None = None
    tws_client_id: int | None = None
    tws_ref_symbol: str | None = None


def fetch_features(
    symbols: Sequence[str],
    *,
    provider: ProviderConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch features for the requested symbols.

    The default provider uses static YAML fixtures for offline iteration. Passing
    ``provider.name='tws-live'`` defers to the IBKR fetcher (requires ibapi).
    """

    provider = provider or ProviderConfig()
    canonical = _canonical_provider(provider.name)
    symbols = [str(sym).upper() for sym in symbols if str(sym).upper()]
    if not symbols:
        return {}

    if canonical == "mock":
        path = _ensure_path(provider.features_path, DEFAULT_FEATURES_PATH)
        text = _read_text(path)
        data = parse_features_yaml(text)
        return {sym: dict(data.get(sym, {})) for sym in symbols if sym in data}

    if canonical == "tws-live":
        if RealTwsFetcher is None or cfg_from_env is None:
            raise RuntimeError("tws-live provider requires ibkr extras; install optipanel[ibkr]")

        if isinstance(provider, ProviderConfig) and any(
            attr is not None
            for attr in (provider.tws_host, provider.tws_port, provider.tws_client_id, provider.tws_ref_symbol)
        ):
            cfg = RealTwsFetcherConfig(
                host=provider.tws_host or "127.0.0.1",
                port=int(provider.tws_port or 7496),
                client_id=int(provider.tws_client_id or 107),
                ref_symbol=str(provider.tws_ref_symbol or "SPY"),
            )
        else:
            cfg = cfg_from_env()

        fetcher = RealTwsFetcher(cfg)
        data = fetcher.features_for_symbols(list(symbols))
        return {sym: dict(data.get(sym, {})) for sym in symbols if sym in data}

    raise ValueError(f"Unsupported provider: {provider.name}")


def _coerce_sequence(value: Any) -> Sequence[Mapping[str, Any]] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return None


def _derive_acceptance(features: Mapping[str, Any]) -> Mapping[str, Any]:
    acceptance = features.get("acceptance")
    if isinstance(acceptance, Mapping):
        return dict(acceptance)

    bars = _coerce_sequence(features.get("recent_bars")) or _coerce_sequence(features.get("bars"))
    level = features.get("breakout_level") or features.get("acceptance_level") or features.get("resistance")
    if bars and isinstance(level, int | float):
        try:
            return detect_breakout_acceptance(bars, float(level))
        except Exception:  # pragma: no cover - defensive safeguard
            return {"armed": False, "accepted": False, "debug": {"error": "acceptance_calc_failed"}}

    return {"armed": False, "accepted": False, "debug": {}}


def compute_panel(
    symbol: str,
    features: Mapping[str, Any],
    *,
    include_supply: bool = True,
    mode: str = "prob",
    battlefield_width: int = 24,
) -> PanelSnapshot:
    """Produce a structured panel snapshot combining recon + battlefield context."""

    symbol = str(symbol).upper()
    features_dict = dict(features)
    snapshot = build_symbol_snapshot(symbol, features_dict)
    recon_entry = build_recon_entry(features_dict, mode=mode, include_supply=include_supply, include_summary=True)

    battlefield = render_battlefield(snapshot.get("units", {}), width=battlefield_width)
    acceptance = _derive_acceptance(features_dict)
    prob_summary = recon_entry.get("chips_summary") or snapshot.get("prob_summary") or {}
    supply = recon_entry.get("supply") if include_supply else None

    return PanelSnapshot(
        symbol=symbol,
        recon_score=int(recon_entry.get("recon", 0)),
        recon=recon_entry,
        readiness=recon_entry.get("readiness", {}),
        sustainment=recon_entry.get("sustainment", {}),
        supply=supply if isinstance(supply, Mapping) else None,
        acceptance=acceptance,
        battlefield=battlefield,
        advice=snapshot.get("advice", "standby"),
        setups=snapshot.get("setups", {}),
        prob_summary=prob_summary,
    )


def budget_status(name: str, budget: Mapping[str, Any] | None) -> BudgetStatus:
    """Map raw budget fields to a compact status/emoji summary."""

    budget = budget or {}
    used = float(budget.get("used_lines", 0) or 0)
    soft_cap = float(budget.get("soft_cap", 0) or 0)
    cooldown = float(budget.get("cooldown", 0) or 0)
    scan_backoff = float(budget.get("scan_stride_backoff", 0) or 0)

    if soft_cap <= 0:
        status = "unknown"
        emoji = "⚪"
    elif used >= soft_cap:
        status = "backoff"
        emoji = "🔴"
    elif cooldown > 0 or scan_backoff > 0:
        status = "cooling"
        emoji = "🟡"
    else:
        status = "ok"
        emoji = "🟢"

    return BudgetStatus(name=name, status=status, emoji=emoji, used=used, soft_cap=soft_cap)


def combine_watchlists(profiles: Profiles) -> list[str]:
    """Return the ordered list of symbols (prime first)."""

    ordered: list[str] = []
    seen: set[str] = set()
    for sym in profiles.prime + profiles.secondary:
        sym_u = sym.upper()
        if sym_u and sym_u not in seen:
            ordered.append(sym_u)
            seen.add(sym_u)
    return ordered


def _build_provider(name: str, features_yaml: str | None) -> Any:
    canonical = _canonical_provider(name)

    if canonical == "tws-live":
        if RealTwsFetcher is None or cfg_from_env is None or TwsFeaturesProvider is None or translate_snapshots is None:
            raise RuntimeError("tws-live provider requires ibkr extras; install optipanel[ibkr]")
        fetcher = RealTwsFetcher(cfg_from_env())
        return TwsFeaturesProvider(fetcher=fetcher, translator=translate_snapshots)

    if MockFeaturesProvider is None:
        raise RuntimeError("Mock provider unavailable; ensure optipanel adapters are installed")

    features = parse_features_yaml(features_yaml) if features_yaml else {}
    return MockFeaturesProvider(features)


def run_tick(
    profiles_yaml_path: str | Path,
    provider_name: str,
    *,
    features_yaml_path: str | Path | None = None,
    width: int = 24,
    top_n: int = 1,
) -> dict[str, Any]:
    """Execute a single scheduler tick and return structured output + panel text."""

    profiles_text = _read_text(profiles_yaml_path)
    profiles = parse_profiles_yaml(profiles_text)
    features_text = _read_text(features_yaml_path) if features_yaml_path else None
    provider = _build_provider(provider_name, features_text)

    run_output = run_profiles_with_provider(profiles, provider, ticks=1)
    panel_text = render_command_room(run_output, width=width, top_n=top_n)
    return {"run": run_output, "panel": panel_text}
