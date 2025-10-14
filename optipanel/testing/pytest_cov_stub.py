"""Optional compatibility helpers when pytest-cov is not installed."""

from __future__ import annotations

import importlib.util
import warnings
from typing import Any


def has_pytest_cov() -> bool:
    """Return True when pytest-cov is importable."""
    return importlib.util.find_spec("pytest_cov") is not None


def register_cov_stubs(parser: Any) -> None:
    """Register no-op coverage options so pytest still parses addopts."""
    group = parser.getgroup("cov (stub)", "coverage options when pytest-cov is absent")
    group.addoption(
        "--cov",
        action="append",
        dest="cov",
        default=[],
        metavar="MODULE",
        help="No-op: install pytest-cov to enable coverage reporting.",
    )
    group.addoption(
        "--cov-report",
        action="append",
        dest="cov_report",
        default=[],
        metavar="TYPE",
        help="No-op: coverage reports unavailable without pytest-cov.",
    )
    group.addoption(
        "--cov-fail-under",
        action="store",
        dest="cov_fail_under",
        default=None,
        metavar="PERCENT",
        type=float,
        help="No-op: minimum coverage requires pytest-cov.",
    )


def maybe_warn_missing_cov(config: Any) -> None:
    """Emit a warning when coverage options are used without pytest-cov."""
    opts = getattr(config, "option", None)
    if opts is None:
        return

    used_cov = bool(getattr(opts, "cov", None))
    used_report = bool(getattr(opts, "cov_report", None))
    fail_under = getattr(opts, "cov_fail_under", None)
    if not (used_cov or used_report or fail_under is not None):
        return

    warnings.warn(
        "pytest-cov is not installed; coverage options are ignored. "
        "Install pytest-cov or pip install .[dev] to enforce coverage thresholds.",
        RuntimeWarning,
        stacklevel=2,
    )
