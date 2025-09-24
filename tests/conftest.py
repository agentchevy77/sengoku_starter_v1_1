"""Project-wide pytest configuration tweaks."""

from __future__ import annotations

from pathlib import Path

import pytest

from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
from optipanel.testing import has_pytest_cov, maybe_warn_missing_cov, register_cov_stubs

FIXTURES = Path(__file__).parents[1] / "config" / "examples"

if not has_pytest_cov():

    def pytest_addoption(parser):  # pragma: no cover - exercised via test run
        register_cov_stubs(parser)

    def pytest_configure(config):  # pragma: no cover - exercised via test run
        maybe_warn_missing_cov(config)


@pytest.fixture(scope="session")
def example_profiles_yaml() -> str:
    return (FIXTURES / "profiles.yaml").read_text()


@pytest.fixture(scope="session")
def example_features_yaml() -> str:
    return (FIXTURES / "features.yaml").read_text()


@pytest.fixture(scope="session")
def example_profiles(example_profiles_yaml: str):
    return parse_profiles_yaml(example_profiles_yaml)


@pytest.fixture(scope="session")
def example_features(example_features_yaml: str):
    return parse_features_yaml(example_features_yaml)
