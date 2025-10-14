from __future__ import annotations

import logging
import os
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    import yaml
except Exception:  # pragma: no cover - fallback when pyyaml missing
    yaml = None

from optipanel import json_utils as json

logger = logging.getLogger(__name__)


class SecretSource(str, Enum):
    """Supported secret backends."""

    ENV = "env"
    FILE = "file"
    AWS = "aws"


def _coerce_source(raw: str | None) -> SecretSource:
    if not raw:
        return SecretSource.ENV
    value = raw.strip().lower()
    for choice in SecretSource:
        if value == choice.value:
            return choice
    logger.warning("Unknown secret source '%s', defaulting to environment", raw)
    return SecretSource.ENV


def _strip(value: Any) -> Any:
    if isinstance(value, str):
        result = value.strip()
        return result if result else None
    return value


def _ensure_mapping(data: Any, origin: str) -> Mapping[str, Any]:
    if isinstance(data, Mapping):
        return data
    raise ValueError(f"Secret payload from {origin} must be a mapping, got {type(data)!r}")


def _check_file_permissions(path: Path, strict: bool = True) -> None:
    """Check if file permissions are secure (not world/group readable).

    Args:
        path: Path to the secrets file
        strict: If True, raise an exception for insecure permissions.
                If False, only log a warning.

    Raises:
        PermissionError: If strict=True and file has insecure permissions
    """
    try:
        file_stat = path.stat()
        mode = file_stat.st_mode

        # Check for world-readable permissions (o+r)
        if mode & stat.S_IROTH:
            msg = (
                f"SECURITY WARNING: Secrets file '{path}' is world-readable "
                f"(mode: {oct(stat.S_IMODE(mode))}). "
                "This allows any user on the system to read your secrets! "
                f"Fix with: chmod 600 {path}"
            )
            if strict:
                raise PermissionError(msg)
            logger.warning(msg)

        # Check for group-readable permissions (g+r)
        elif mode & stat.S_IRGRP:
            msg = (
                f"SECURITY WARNING: Secrets file '{path}' is group-readable "
                f"(mode: {oct(stat.S_IMODE(mode))}). "
                "This allows other users in your group to read your secrets. "
                f"Fix with: chmod 600 {path}"
            )
            if strict:
                raise PermissionError(msg)
            logger.warning(msg)

        # Check for recommended permissions (owner read-only or read-write)
        elif not (
            (mode & stat.S_IRUSR)
            and not (mode & (stat.S_IWGRP | stat.S_IWOTH | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        ):
            # File should be readable by owner, not writable/executable by group/others
            perms = stat.S_IMODE(mode)
            if perms not in (0o600, 0o400):  # Accept both read-write and read-only for owner
                logger.info(
                    "Secrets file '%s' has permissions %s. " "Consider using more restrictive permissions (600 or 400)",
                    path,
                    oct(perms),
                )
    except PermissionError:
        # Re-raise PermissionError for insecure file permissions
        raise
    except OSError as e:
        # Log other OS errors (e.g., file not found during stat)
        logger.warning("Could not check permissions for secrets file '%s': %s", path, e)
        # Don't fail on permission check errors - let the file loading fail naturally


@dataclass
class SecretResolver:
    """Resolve secrets from environment, local files, or cloud providers."""

    source: SecretSource = SecretSource.ENV
    env: Mapping[str, str] | None = None
    file_path: str | os.PathLike[str] | None = None
    aws_secret_id: str | None = None
    strict_permissions: bool = True  # Fail on insecure file permissions by default
    _loader: Callable[[str], Mapping[str, Any]] | None = None

    def __post_init__(self) -> None:
        self._env = dict(self.env or os.environ)
        self._data: dict[str, Any] = {}
        if self.source == SecretSource.FILE:
            path = Path(self.file_path or "").expanduser()
            self._data = dict(self._load_file(path))
        elif self.source == SecretSource.AWS:
            secret_id = self.aws_secret_id or self._env.get("SENGOKU_AWS_SECRET_ID")
            if not secret_id:
                raise ValueError("AWS secret source requires 'aws_secret_id'")
            self._data = dict(self._load_aws(secret_id))

    @classmethod
    def from_environment(cls) -> SecretResolver:
        source = _coerce_source(os.getenv("SENGOKU_SECRETS_SOURCE"))
        file_path = os.getenv("SENGOKU_SECRETS_FILE")
        aws_secret_id = os.getenv("SENGOKU_AWS_SECRET_ID")
        # Allow overriding strict mode via environment variable
        strict_env = os.getenv("SENGOKU_SECRETS_STRICT_PERMISSIONS", "true")
        strict_permissions = strict_env.lower() not in ("false", "0", "no", "off")
        return cls(
            source=source, file_path=file_path, aws_secret_id=aws_secret_id, strict_permissions=strict_permissions
        )

    # ----- public API -----
    def resolve(
        self,
        key: str,
        *,
        default: Any = None,
        required: bool = False,
        cast: Callable[[Any], Any] | None = None,
        validator: Callable[[Any], bool] | None = None,
        redact: bool = True,
    ) -> Any:
        raw = self._data.get(key)
        if raw is None:
            raw = self._env.get(key)
        raw = _strip(raw)
        if raw is None:
            if required:
                raise KeyError(f"Missing required secret '{key}'")
            return default
        value = cast(raw) if cast else raw
        if validator and not validator(value):
            raise ValueError(f"Secret '{key}' failed validation")
        if redact:
            logger.debug("Resolved secret '%s' from %s", key, self.source.value)
        else:
            logger.debug("Resolved secret '%s'=%s", key, value)
        return value

    def require_str(self, key: str) -> str:
        return str(self.resolve(key, required=True, cast=str))

    def get_str(self, key: str, default: str | None = None, *, required: bool = False) -> str | None:
        result = self.resolve(key, default=default, required=required, cast=str)
        return str(result) if result is not None else None

    def get_int(self, key: str, default: int | None = None, *, required: bool = False) -> int | None:
        result = self.resolve(key, default=default, required=required, cast=lambda v: int(str(v)))
        return int(result) if result is not None else None

    def get_float(self, key: str, default: float | None = None, *, required: bool = False) -> float | None:
        result = self.resolve(key, default=default, required=required, cast=lambda v: float(str(v)))
        return float(result) if result is not None else None

    def get_bool(self, key: str, default: bool = False) -> bool:
        truthy = {"1", "true", "yes", "on"}
        falsy = {"0", "false", "no", "off"}
        raw = self.resolve(key, default=None, cast=str, redact=True)
        if raw is None:
            return default
        value = raw.strip().lower()
        if value in truthy:
            return True
        if value in falsy:
            return False
        raise ValueError(f"Secret '{key}' cannot be parsed as boolean")

    # ----- loaders -----
    def _load_file(self, path: Path) -> Mapping[str, Any]:
        if not path:
            raise ValueError("Secret source FILE requires 'file_path'")
        if not path.exists():
            raise FileNotFoundError(f"Secrets file not found: {path}")

        # Check file permissions for security vulnerabilities
        _check_file_permissions(path, strict=self.strict_permissions)

        text = path.read_text().strip()
        if not text:
            logger.warning("Secrets file '%s' is empty", path)
            return {}
        loader = self._loader or self._detect_loader(path)
        payload = loader(text)
        return _ensure_mapping(payload, str(path))

    def _detect_loader(self, path: Path) -> Callable[[str], Mapping[str, Any]]:
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise RuntimeError("PyYAML required to load YAML secrets")

            def load_yaml(data: str) -> Mapping[str, Any]:
                return _ensure_mapping(yaml.safe_load(data) or {}, str(path))

            return load_yaml

        def load_json(data: str) -> Mapping[str, Any]:
            return _ensure_mapping(json.loads(data or "{}"), str(path))

        return load_json

    def _load_aws(self, secret_id: str) -> Mapping[str, Any]:  # pragma: no cover - requires boto3
        try:
            import boto3
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("boto3 is required for AWS secret resolution") from exc

        client = boto3.session.Session().client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_id)
        payload = response.get("SecretString")
        if not payload:
            raise ValueError(f"Secret '{secret_id}' did not return a SecretString")
        return _ensure_mapping(json.loads(payload), f"aws:{secret_id}")


def resolve_secret(key: str, **kwargs: Any) -> Any:
    resolver = SecretResolver.from_environment()
    return resolver.resolve(key, **kwargs)
