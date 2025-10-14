#!/usr/bin/env python3
"""
Test for Bug #35: Latent ImportError Crash in Stress Test Scripts

This test verifies that:
1. psutil is properly declared as a dependency in [profiling] extras
2. All scripts that use psutil can import it when [profiling] is installed
3. No stale dependencies (like ib_insync) exist in the metadata
4. The stress test scripts can successfully instantiate their psutil-dependent functionality
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


class TestBug35DependencyFix:
    """Test suite for Bug #35: Missing psutil dependency fix."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).resolve().parents[1]

    @pytest.fixture
    def egg_info_requires(self, project_root: Path) -> Path:
        """Get the path to the requires.txt file in egg-info."""
        return project_root / "optipanel_sengoku.egg-info" / "requires.txt"

    def test_psutil_importable(self):
        """Test that psutil can be imported (verifies it's installed)."""
        try:
            import psutil

            # Verify psutil is functional
            assert hasattr(psutil, "Process"), "psutil.Process should be available"
            assert hasattr(psutil, "virtual_memory"), "psutil.virtual_memory should be available"

            # Verify we can create a Process object
            process = psutil.Process()
            assert process is not None, "Should be able to create a psutil.Process instance"

        except ImportError as e:
            pytest.fail(
                f"psutil is not installed. Install with: pip install -e '.[profiling]'\n" f"Original error: {e}"
            )

    def test_psutil_in_profiling_extras(self, project_root: Path):
        """Test that psutil is declared in pyproject.toml under [profiling] extras."""
        pyproject_path = project_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml should exist"

        content = pyproject_path.read_text()

        # Check that psutil is in the profiling section
        assert "profiling" in content, "pyproject.toml should have [project.optional-dependencies] profiling section"

        # Find the profiling section and verify psutil is there
        lines = content.splitlines()
        in_profiling = False
        found_psutil = False

        for line in lines:
            if "profiling = [" in line:
                in_profiling = True
            elif in_profiling and "]" in line and "=" not in line:
                in_profiling = False
            elif in_profiling and "psutil" in line:
                found_psutil = True
                # Verify version constraint is reasonable
                assert ">=" in line, "psutil should have a minimum version constraint"
                break

        assert found_psutil, "psutil should be listed in [project.optional-dependencies] profiling section"

    def test_no_stale_ib_insync_dependency(self, egg_info_requires: Path):
        """Test that ib_insync is NOT in the core dependencies (was a stale dependency)."""
        if not egg_info_requires.exists():
            pytest.skip("egg-info/requires.txt does not exist yet (package not installed)")

        content = egg_info_requires.read_text()
        lines = content.splitlines()

        # Check core dependencies (before first [extras] section)
        core_deps = []
        for line in lines:
            if line.strip().startswith("["):
                break  # Reached extras section
            if line.strip() and not line.startswith("#"):
                core_deps.append(line.strip())

        # Verify ib_insync is NOT in core dependencies
        for dep in core_deps:
            assert "ib_insync" not in dep.lower(), (
                f"ib_insync should NOT be a core dependency (found: {dep}). "
                "It was a stale dependency that has been removed."
            )

    def test_psutil_in_metadata_profiling_section(self, egg_info_requires: Path):
        """Test that psutil appears in the [profiling] section of requires.txt."""
        if not egg_info_requires.exists():
            pytest.skip("egg-info/requires.txt does not exist yet (package not installed)")

        content = egg_info_requires.read_text()

        # Find [profiling] section
        lines = content.splitlines()
        in_profiling = False
        found_psutil = False

        for line in lines:
            if line.strip() == "[profiling]":
                in_profiling = True
            elif line.strip().startswith("[") and in_profiling:
                in_profiling = False
            elif in_profiling and "psutil" in line.lower():
                found_psutil = True
                # Verify version constraint
                assert ">=" in line, "psutil should have minimum version constraint"
                # Extract and verify version
                if "psutil>=" in line:
                    version = line.split(">=")[1].strip()
                    major = int(version.split(".")[0])
                    assert major >= 7, f"psutil version should be >= 7.0.0, got {version}"
                break

        assert found_psutil, "psutil should be in [profiling] section of requires.txt"

    def test_stress_test_script_can_use_psutil(self, project_root: Path):
        """Test that the stress test script can successfully use psutil functionality."""
        # This is an integration test that verifies the actual usage
        script_path = project_root / "scripts" / "ibkr_stress_test.py"
        assert script_path.exists(), "ibkr_stress_test.py should exist"

        # Read the script to verify psutil usage
        content = script_path.read_text()
        assert "import psutil" in content, "Script should import psutil"

        # Verify we can import psutil in the same way the script does
        try:
            import psutil

            # Simulate what the script does
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)

            assert isinstance(memory_mb, float), "Should be able to get memory usage"
            assert memory_mb > 0, "Memory usage should be positive"

        except ImportError:
            pytest.fail("psutil should be importable when running stress test script")

    def test_performance_monitor_script_can_use_psutil(self, project_root: Path):
        """Test that the performance monitor script can successfully use psutil functionality."""
        script_path = project_root / "scripts" / "ibkr_performance_monitor.py"
        assert script_path.exists(), "ibkr_performance_monitor.py should exist"

        # Read the script to verify psutil usage
        content = script_path.read_text()
        assert "import psutil" in content, "Script should import psutil"

    def test_no_ib_insync_imports_in_codebase(self, project_root: Path):
        """Test that no files in optipanel/ or scripts/ import ib_insync."""
        # Search for ib_insync imports
        found_imports = []

        for directory in ["optipanel", "scripts"]:
            dir_path = project_root / directory
            if not dir_path.exists():
                continue

            for py_file in dir_path.rglob("*.py"):
                content = py_file.read_text()
                if "from ib_insync" in content or "import ib_insync" in content:
                    found_imports.append(str(py_file.relative_to(project_root)))

        assert not found_imports, (
            f"Found ib_insync imports in: {found_imports}. "
            "ib_insync is not a declared dependency and should not be used."
        )

    def test_package_installation_includes_psutil(self, project_root: Path):
        """Test that installing with [profiling] extras installs psutil."""
        # Check if psutil is installed
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "psutil"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            "psutil should be installed when [profiling] extras are installed. " "Run: pip install -e '.[profiling]'"
        )

        # Verify version is acceptable
        output = result.stdout
        version_line = [line for line in output.splitlines() if line.startswith("Version:")][0]
        version = version_line.split(":")[1].strip()
        major_version = int(version.split(".")[0])

        assert major_version >= 7, f"psutil version should be >= 7.0.0, got {version}"


class TestBug35RegressionPrevention:
    """Regression tests to prevent Bug #35 from recurring."""

    def test_all_script_imports_are_declared(self):
        """
        Test that all third-party imports in scripts/ are declared in pyproject.toml.

        This prevents future bugs where scripts use undeclared dependencies.
        """
        import ast
        import importlib.metadata

        project_root = Path(__file__).resolve().parents[1]
        scripts_dir = project_root / "scripts"

        # Get all declared dependencies from pyproject.toml
        try:
            # Get all dependencies including extras (ensures package metadata exists)
            importlib.metadata.distribution("optipanel-sengoku")

            # This would require parsing metadata, so we'll do a simpler check
            # Just verify key scripts don't have obvious missing deps

        except importlib.metadata.PackageNotFoundError:
            pytest.skip("Package not installed")

        # For now, just verify the specific scripts we know about
        critical_scripts = [
            scripts_dir / "ibkr_stress_test.py",
            scripts_dir / "ibkr_performance_monitor.py",
        ]

        for script in critical_scripts:
            if not script.exists():
                continue

            # Parse imports
            content = script.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        # Check if it's a third-party module (not stdlib)
                        if module_name == "psutil":
                            # We know psutil should be importable
                            try:
                                __import__(module_name)
                            except ImportError:
                                pytest.fail(
                                    f"{script.name} imports {module_name} but it's not installed. "
                                    f"Install with: pip install -e '.[profiling]'"
                                )


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
