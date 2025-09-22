"""Project-wide pytest configuration tweaks."""

from __future__ import annotations

from optipanel.testing import has_pytest_cov, maybe_warn_missing_cov, register_cov_stubs

if not has_pytest_cov():

    def pytest_addoption(parser):  # pragma: no cover - exercised via test run
        register_cov_stubs(parser)

    def pytest_configure(config):  # pragma: no cover - exercised via test run
        maybe_warn_missing_cov(config)
