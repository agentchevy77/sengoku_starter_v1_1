# Claude Assistant Instructions for Sengoku Project

## Final Bug Status Summary (Masterclass Complete)
**Total Bugs Identified by Masterclass Debugger**: 41
**Total Bugs Fixed**: 36
**Remaining Unresolved Bugs**: 5 (0 Critical, 1 High, 4 Medium, 0 Low)
**Verified False Positives**: 2

---

## Recent Changes

### 2025-10-03: Critical Mathematical Accuracy Fix (Bug #36)
**Status**: ✅ **FIXED**
- **Bug #36 (Systemic Mathematical Inaccuracy)**: Completely resolved the critical issue of using `float` for financial calculations. The codebase now uses Python's `Decimal` type throughout, ensuring penny-perfect arithmetic with no rounding errors. Created comprehensive decimal utilities module (`optipanel/utils/decimal_types.py`) and updated all financial calculation modules. All 26 tests pass with exact precision verified.

### 2025-10-03: Type Consistency Fix (Bug #34)
**Status**: ✅ **FIXED**
- **Bug #34 (Inconsistent Data Types in Snapshot)**: Eliminated mixed `int`/`float` types in score-related fields by removing the `debug` sub-dictionary from `compute_sustainment()`. All score fields now consistently return `int` (0-100 range), eliminating API consumer ambiguity.

### 2025-10-03: Configuration File Error Handling Fix (Bug #31)
**Status**: ✅ **FIXED**
- **Bug #31 (Unhandled Read Error on Configuration Files)**: The `_read_text()` function in `optipanel/ui/service.py` now includes comprehensive error handling for all I/O errors. A new `ConfigurationFileError` exception wraps `PermissionError`, `FileNotFoundError`, `IsADirectoryError`, and generic `OSError` with actionable error messages and preserved exception chains for debugging.

### 2025-10-03: Critical Security Vulnerabilities Fixed (Bugs #40-41)
**Status**: ✅ **BOTH FIXED**
- **Bug #40 (RCE Vulnerability)**: Verified that all application code correctly uses `yaml.safe_load()`, neutralizing the vulnerability.
- **Bug #41 (Insecure File Permissions)**: Confirmed that `optipanel/security/secrets.py` now contains a `_check_file_permissions()` function that validates permissions on secrets files and will raise a `PermissionError` in strict mode.

### 2025-10-03: Core Logic and Configuration Fixes (Bugs #27, #28, #29, #32, #37)
**Status**: ✅ **ALL FIXED**
- **Bug #32 (Dangerous Advice Logic)**: The `_get_advice` logic in `optipanel/engine/aggregate.py` has been refactored to include multi-factor risk assessment, preventing "attack" recommendations on over-extended symbols.
- **Bugs #27 & #28 (Scan Engine Crash Risks)**: The `run_local_scan` function in `optipanel/engine/scan.py` now uses `.get()` with default values, preventing `KeyError` crashes.
- **Bug #29 (Redundant Processing)**: The unnecessary `sorted()` call in `optipanel/engine/scan.py` has been removed.
- **Bug #37 (Ambiguous Watchlist Config)**: The duplicate "TSLA" entry has been removed from `config/examples/live_profiles.yaml`.

---

## Known Issues (Final Unresolved List)

The following 5 bugs, identified during the Masterclass Debugging sessions, are the final unresolved issues in the codebase.

#### 🟠 HIGH

1.  **Bug #33: Final Score Calculation Ignores Key Risk Metric**
    - **Location**: `optipanel/engine/aggregate.py`
    - **Threat**: The final `score` used for ranking symbols is blind to the `sustainment` and `exhaustion` risk metrics, leading to a flawed and unreliable "top" list.

#### 🟡 MEDIUM

1.  **Bug #39: Misleading Default Parameter in Core Algorithm**
    - **Location**: `optipanel/engine/aggregate.py`
    - **Threat**: A critical `sustain_thresh` is hidden as a default argument, making the system's advice logic nearly impossible to configure correctly.

2.  **Bug #38: Lack of Edge-Case Scenarios in Mock Data**
    - **Location**: `config/examples/features.yaml`
    - **Threat**: The mock data used for testing contains no edge cases, giving a false sense of security.

3.  **Bug #35: Latent `ImportError` Crash in Unmaintained Script**
    - **Location**: `scripts/ibkr_stress_test_demo.py`
    - **Threat**: A forgotten script imports a library (`ib_insync`) that is not a project dependency, guaranteeing a crash if run.

4.  **Bug #30: Multi-Process Race Condition in Log Rotation**
    - **Location**: `optipanel/ops/session_logger_safe.py`
    - **Threat**: The logger's file rotation logic is not safe for multiple concurrent processes, which can lead to crashes or failed rotations.

---

*Last Updated: 2025-10-03*