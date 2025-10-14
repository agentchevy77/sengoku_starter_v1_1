"""Testing utilities (no runtime dependencies)."""

__all__ = [
    "has_pytest_cov",
    "register_cov_stubs",
    "maybe_warn_missing_cov",
]

from .pytest_cov_stub import has_pytest_cov, maybe_warn_missing_cov, register_cov_stubs
