# Dependency Compatibility Audit

A lightweight CLI is now available to ensure `pyproject.toml` has no conflicting
version constraints. The tool lives at `scripts/check_dependency_compatibility.py`
and can be invoked via:

```bash
.venv/bin/python scripts/check_dependency_compatibility.py
```

It scans core + optional dependency groups, warning when incompatible pins or
range overlaps are detected. CI should invoke this script whenever dependency
specs are updated.
