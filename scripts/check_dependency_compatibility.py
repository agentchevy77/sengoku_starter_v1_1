#!/usr/bin/env python3
"""CLI helper to audit project dependencies for compatibility issues."""

from __future__ import annotations

from optipanel.utils.dependency_audit import main

if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
