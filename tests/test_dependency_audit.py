from __future__ import annotations

from packaging.requirements import Requirement

from optipanel.utils import dependency_audit


def test_conflict_detected_for_disjoint_pins():
    reqs = {
        "demo": [
            dependency_audit.RequirementEntry("group_a", Requirement("demo==1.0.0")),
            dependency_audit.RequirementEntry("group_b", Requirement("demo==2.0.0")),
        ]
    }

    issues = dependency_audit.find_conflicts(reqs)
    assert issues and issues[0]["package"] == "demo"


def test_no_conflict_for_overlapping_ranges():
    reqs = {
        "tool": [
            dependency_audit.RequirementEntry("alpha", Requirement("tool>=1.0,<3.0")),
            dependency_audit.RequirementEntry("beta", Requirement("tool>=2.0")),
        ]
    }

    issues = dependency_audit.find_conflicts(reqs)
    assert not issues


def test_conflict_for_non_overlapping_bounds():
    reqs = {
        "lib": [
            dependency_audit.RequirementEntry("x", Requirement("lib<1.0")),
            dependency_audit.RequirementEntry("y", Requirement("lib>=1.0")),
        ]
    }

    issues = dependency_audit.find_conflicts(reqs)
    assert issues and issues[0]["package"] == "lib"


def test_exact_pin_checked_against_range():
    reqs = {
        "pkg": [
            dependency_audit.RequirementEntry("core", Requirement("pkg==1.2.0")),
            dependency_audit.RequirementEntry("extra", Requirement("pkg>=1.0,<2.0")),
        ]
    }

    issues = dependency_audit.find_conflicts(reqs)
    assert not issues


def test_audit_pyproject_detects_conflict(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["demo==1.0.0"]

[project.optional-dependencies]
extra = ["demo==2.0.0"]
"""
    )

    issues = dependency_audit.audit_pyproject(pyproject)
    assert issues and issues[0]["package"] == "demo"


def test_audit_pyproject_reports_clean_state(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["demo>=1.0"]

[project.optional-dependencies]
extra = ["demo<3.0"]
"""
    )

    issues = dependency_audit.audit_pyproject(pyproject)
    assert not issues
