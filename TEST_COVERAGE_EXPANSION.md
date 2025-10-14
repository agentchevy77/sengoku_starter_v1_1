# Test Coverage Expansion Notes

_Last updated: 2025-09-24_

## Current Snapshot
- **Overall line coverage:** ~86.9% (goal ≥61% met)
- **Test suite:** `pytest -q` (skips marked slow tests); FastAPI/Textual extras installed so new modules are exercised
- **Key additions covered:**
  - `optipanel.ui.service` – unit tests in `tests/test_ui_service.py`
  - `optipanel.api.app` – endpoint coverage in `tests/test_api_app.py`
  - Session logger, command room, scheduler suites unchanged and still green

## Targeted Gap Areas

### 1. `optipanel.recon.gating` (~65% line coverage)
- Uncovered lines: 14, 19, 21-23, 27, 29-33, 48-51, 65-72, 75-79, 93
- Missing scenarios: readiness thresholds, `require_acceptance` path, armed floor filtering, invalid acceptance payloads
- **Next step:** parameterize a test that toggles each gate combination to ensure branches flip between GO / HOLD states

### 2. `optipanel.ops.dependency_guard` (~57%)
- Uncovered lines: 32, 48, 58-68, 78-102, 119-121, 168-184
- Missing scenarios: import failures, forbidden modules, duplicate dependency declarations
- **Next step:** monkeypatch `importlib.import_module` and supply synthetic configs to verify diagnostics and exit codes

### 3. `optipanel.ops.session_logger_safe` (~75%)
- Uncovered defensive branches: 105-139, 152-161, 192-210, 223-225, 265-319, 354, 379-475, 492-521, 529
- Missing scenarios: rotation errors, JSON serialization failures, locked file cleanup, concurrent emit recovery
- **Next step:** patch underlying logger/rotation manager to throw exceptions and assert safe logger swallows failures while incrementing error counters

### 4. Textual UI (`optipanel/ui/textual/app.py`, `minimal.py`)
- Currently untested (manual exercise only)
- **Next step:** use Textual’s test harness to snapshot the watchlist table, simulate refresh hotkeys, and verify error states

### 5. Miscellaneous low-coverage legacy modules
- `optipanel/testing/pytest_cov_stub.py` (38%) – informational only, low priority
- IBKR adapters (`mock_provider`, `tws_fetcher`, etc.) – most uncovered lines correspond to live TWS branches; consider stub-based tests when we formalize integration suite

## Suggested Work Plan

| Priority | Area | Action |
| --- | --- | --- |
| High | Recon gating | Add branch tests covering acceptance/readiness permutations |
| High | Dependency guard | Simulate missing/blocked imports, verify error logging |
| High | Session logger safe | Force error conditions (rotation, emit) and assert graceful handling |
| Medium | Textual UI | Add basic snapshot/smoke tests using Textual testing utilities |
| Medium | TWS fetcher | Extend fake TWS session to cover pacing/timeout recovery |
| Low | Pytest cov stub | Optional tidy-up if we want 50%+ coverage on meta tooling |

## Quick-Win Test Sketches

```python
# tests/test_recon_gating.py
@pytest.mark.parametrize(
    "gate_config",
    [
        {"require_acceptance": True, "armed_floor": 60, "ready_min": 65},
        {"require_acceptance": False, "armed_floor": 40, "ready_min": 50},
    ],
)
def test_gate_decision_variants(gate_config, recon_entry_factory):
    gate = compute_gate_for_snapshot(
        recon_entry_factory(armed=70, readiness=70, accepted=True),
        **gate_config,
    )
    assert gate in {"go", "hold"}
```

```python
# tests/test_dependency_guard.py
import importlib
from optipanel.ops.dependency_guard import ensure_dependencies

def test_dependency_guard_reports_missing_module(monkeypatch, tmp_path):
    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError(name)))
    with pytest.raises(RuntimeError):
        ensure_dependencies({"required": ["missing_pkg"]})
```

```python
# tests/test_session_logger_safe.py
from optipanel.ops.session_logger_safe import SafeSessionLogger

def test_safe_logger_handles_emit_exception(monkeypatch, tmp_path):
    logger = SafeSessionLogger(log_dir=tmp_path)
    monkeypatch.setattr(logger._logger, "emit", lambda *a, **k: (_ for _ in ()).throw(IOError("disk full")))
    logger.emit("test", {})
    logger.finalize()
    assert logger._metadata.error_count > 0
```

## Summary
Coverage is healthy, and all new functionality landed with tests. The next wave of gains comes from tightening legacy guardrails (gating, dependency guard, safe logger) and introducing automated coverage for the Textual UI. None of these are blockers, but tackling them will move overall coverage toward 90% and increase confidence in failure handling.

## Quick Summary for Stakeholders

- **Critical gaps:** Recon gating (branch logic), dependency guard (missing-package paths), safe session logger (error fallbacks), and Textual UI (UI smoke tests).
- **New code covered:** API endpoints and shared UI service already have unit coverage when dependencies are present.
- **Next steps:** Prioritize tests that hit defensive/error paths and add Textual snapshot tests if we want automated UI coverage.
