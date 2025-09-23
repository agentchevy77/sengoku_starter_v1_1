"""Regression tests that prevent documentation rot in critical modules."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

MODULE_FUNCTIONS = {
    "optipanel.ops.ops_loop": [
        "run_watchlist_once",
        "make_scheduler_from_profile",
        "ops_loop",
    ],
    "optipanel.ops.ops_loop_enhanced": [
        "run_watchlist_once_with_logging",
        "make_scheduler_from_profile",
        "ops_loop_enhanced",
    ],
    "scripts.metrics.watchlist_dashboard": [
        "iter_events",
        "summarize",
        "parse_args",
        "main",
    ],
}


@pytest.mark.parametrize("module_path", MODULE_FUNCTIONS.keys())
def test_module_and_function_docstrings(module_path: str) -> None:
    """Assert that designated modules and functions remain documented."""

    module = importlib.import_module(module_path)
    assert inspect.getdoc(module), f"{module_path} lacks a module docstring"

    for func_name in MODULE_FUNCTIONS[module_path]:
        func = getattr(module, func_name)
        assert inspect.getdoc(func), f"{module_path}.{func_name} is missing a docstring"


def test_architecture_overview_exists() -> None:
    """Ensure the architecture documentation stays present and informative."""

    doc_path = Path("docs/ARCHITECTURE.md")
    assert doc_path.exists(), "Architecture overview is missing"
    content = doc_path.read_text(encoding="utf-8")
    for keyword in ("Interfaces", "Runtime", "Engines", "Adapters", "Performance Benchmarks"):
        assert keyword in content, f"Architecture doc missing keyword: {keyword}"


@pytest.mark.parametrize(
    "doc_path,keywords",
    [
        (Path("docs/API_REFERENCE.md"), ("Command-Line Interfaces", "Planned REST API")),
        (Path("docs/ERROR_CODES.md"), ("Process Exit Codes", "Session Logger Error Types")),
        (Path("docs/TROUBLESHOOTING.md"), ("Troubleshooting Guide", "Performance Regression Detected")),
    ],
)
def test_operational_docs_present(doc_path: Path, keywords: tuple[str, ...]) -> None:
    """Verify that operational documentation files exist and include key sections."""

    assert doc_path.exists(), f"Required documentation missing: {doc_path}"
    content = doc_path.read_text(encoding="utf-8")
    for keyword in keywords:
        assert keyword in content, f"{doc_path.name} missing keyword: {keyword}"
