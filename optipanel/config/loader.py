"""
Application configuration loader backed by Pydantic models.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    from .models import AppConfigModel, SetupConfigModel, TwsConfigModel, UIConfigModel
except ImportError:  # pragma: no cover - transitional fallback
    try:
        from optipanel.config.models import AppConfigModel, SetupConfigModel, TwsConfigModel, UIConfigModel
    except ImportError:  # pragma: no cover
        logging.error("Configuration models not found; falling back to inert stubs.")
        AppConfigModel = SetupConfigModel = TwsConfigModel = UIConfigModel = object  # type: ignore[misc, assignment]

try:
    from pydantic import ValidationError
except ImportError:  # pragma: no cover
    ValidationError = Exception  # type: ignore[assignment]

try:
    from optipanel.json_utils import JSONDecodeError
    from optipanel.json_utils import loads as json_loads
except ImportError:  # pragma: no cover
    import json

    json_loads = json.loads
    JSONDecodeError = json.JSONDecodeError  # type: ignore[attr-defined]

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or validated."""


def _load_config_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists() or not file_path.is_file():
        raise ConfigError(f"Configuration file not found: {file_path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise ConfigError(f"Error reading configuration file {file_path}: {exc}") from exc

    suffix = file_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        if yaml is None:
            raise ConfigError(f"PyYAML not installed; cannot read {file_path}")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error parsing configuration file {file_path}: {exc}") from exc
    elif suffix == ".json":
        try:
            data = json_loads(text)
        except JSONDecodeError as exc:
            raise ConfigError(f"Error parsing configuration file {file_path}: {exc}") from exc
    else:
        raise ConfigError(f"Unsupported configuration format: {suffix}")

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file {file_path} must contain a mapping at the root.")

    return data


def resolve_secrets() -> dict[str, str]:
    secrets: dict[str, str] = {}
    if host := os.getenv("SENGOKU_SECRET_TWS_HOST"):
        secrets["TWS_HOST"] = host
    if port := os.getenv("SENGOKU_SECRET_TWS_PORT"):
        secrets["TWS_PORT"] = port
    return secrets


def _load_config_from_env() -> dict[str, Any]:
    overrides: dict[str, dict[str, Any]] = {"tws": {}, "ui": {}, "setups": {}}
    secrets = resolve_secrets()

    if host := secrets.get("TWS_HOST") or os.getenv("SENGOKU_TWS_HOST"):
        overrides["tws"]["host"] = host
    if port := secrets.get("TWS_PORT") or os.getenv("SENGOKU_TWS_PORT"):
        overrides["tws"]["port"] = port
    if rate := os.getenv("SENGOKU_TWS_RATE_LIMIT"):
        overrides["tws"]["rate_limit"] = rate
    if ref := os.getenv("SENGOKU_TWS_REF"):
        overrides["tws"]["ref_symbol"] = ref

    if refresh := os.getenv("SENGOKU_UI_REFRESH_INTERVAL"):
        overrides["ui"]["refresh_interval"] = refresh

    if trend := os.getenv("SENGOKU_SETUP_TREND_THRESHOLD"):
        overrides["setups"]["trend_threshold"] = trend

    return {key: value for key, value in overrides.items() if value}


def _resolve_runtime_dirs() -> dict[str, Path]:
    override = os.getenv("SENGOKU_RUNTIME_DIR")
    if override:
        base = Path(override).expanduser().resolve()
        mapping = {
            "logs": base / "logs",
            "cache": base / "cache",
            "state": base / "state",
            "config": base / "config",
        }
    else:
        home = Path.home()
        cache_home = Path(os.getenv("XDG_CACHE_HOME", home / ".cache"))
        state_home = Path(os.getenv("XDG_STATE_HOME", home / ".local/state"))
        config_home = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
        mapping = {
            "logs": state_home / "sengoku/logs",
            "cache": cache_home / "sengoku",
            "state": state_home / "sengoku",
            "config": config_home / "sengoku",
        }

    for directory in mapping.values():
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name == "posix" and (directory.stat().st_mode & 0o777) != 0o700:
                directory.chmod(0o700)
        except OSError as exc:  # pragma: no cover - filesystem errors
            logger.warning("Could not prepare runtime directory %s: %s", directory, exc)

    return mapping


def load_app_config(config_path: Path | None = None) -> AppConfigModel:
    if AppConfigModel is object:
        raise ConfigError("Configuration models unavailable; aborting load.")

    config_data: dict[str, Any] = {}
    if config_path is not None:
        try:
            file_data = _load_config_file(config_path)
        except ConfigError as exc:
            logger.error("Failed to load configuration file: %s", exc)
        else:
            for section, values in file_data.items():
                if section in config_data and isinstance(config_data[section], dict) and isinstance(values, dict):
                    config_data[section].update(values)
                else:
                    config_data[section] = values
            logger.info("Loaded configuration from %s", config_path)

    env_overrides = _load_config_from_env()
    for section, values in env_overrides.items():
        if section in config_data and isinstance(config_data[section], dict):
            config_data[section].update(values)
        else:
            config_data[section] = values

    try:
        config = AppConfigModel(**config_data)
    except ValidationError as exc:
        logger.error("Configuration validation failed:")
        for error in exc.errors():
            loc = " -> ".join(map(str, error["loc"]))
            msg = error["msg"]
            input_value = error.get("input", "<unknown>")
            logger.error("  [%s] %s (input: %r)", loc, msg, input_value)
        raise ConfigError("Invalid configuration structure or values.") from exc
    except Exception as exc:  # pragma: no cover - unexpected failures
        logger.exception("Unexpected error while loading configuration.")
        raise ConfigError("Failed to initialise application configuration.") from exc

    mapping = _resolve_runtime_dirs()
    config.runtime_dirs = {key: str(path) for key, path in mapping.items()}

    logger.info("Application configuration loaded and validated successfully.")
    return config


if AppConfigModel is not object:
    AppConfig = AppConfigModel
    __all__ = [
        "load_app_config",
        "ConfigError",
        "AppConfig",
        "SetupConfigModel",
        "TwsConfigModel",
        "UIConfigModel",
        "resolve_secrets",
    ]
else:  # pragma: no cover - transitional fallback
    __all__ = ["load_app_config", "ConfigError", "resolve_secrets"]


def parse_profiles_yaml(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text) or {}
    wl = data.get("watchlists") or data.get("lists") or {}
    bd = data.get("budgets") or {}
    ui = data.get("ui") or {}
    watchlists = {str(k): list(v or []) for k, v in (wl or {}).items()}
    budgets = {str(k): dict(v or {}) for k, v in (bd or {}).items()}
    ui_out = {"width": int(ui.get("width", 24)), "top_n": int(ui.get("top_n", 1))}
    return {"watchlists": watchlists, "budgets": budgets, "ui": ui_out}


def parse_features_yaml(text: str) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(text) or {}
    out: dict[str, dict[str, Any]] = {}
    for sym, feats in (data or {}).items():
        if isinstance(feats, dict):
            out[str(sym)] = dict(feats)
    return out


def load_profiles_yaml(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return parse_profiles_yaml(text)
