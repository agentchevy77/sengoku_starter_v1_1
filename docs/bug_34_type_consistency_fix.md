# Bug #34 Fix: Inconsistent Data Types in Snapshot

## Overview
**Severity**: 🟢 LOW
**Status**: ✅ **FIXED**
**Location**: `optipanel/engine/aggregate.py`, `optipanel/chips/aggregate.py`
**Date Fixed**: 2025-10-03

## Problem Statement

### Original Threat
The symbol snapshot returned by `build_symbol_snapshot()` contained score-related fields using a mix of `int` and `float` types, creating ambiguity for API consumers:

- Most score fields: `int` (0-100 range) ✓
- `sustainment["debug"]`: `float` values ❌

This type inconsistency violated the principle of least surprise and made it difficult for API consumers to handle responses uniformly.

### Root Cause
The `compute_sustainment()` function returned a dictionary containing:
```python
{
    "sustainability": int,      # 0-100 score
    "fakeout_risk": int,        # 0-100 score
    "debug": {                  # Diagnostic data
        "trend": float,         # ❌ Raw float value
        "counter": float,       # ❌ Raw float value
        ...
    }
}
```

The `debug` sub-dictionary contained intermediate calculation values as floats, which were included in the snapshot alongside all other score fields that were integers.

## Solution

### Approach
**Selected**: Remove debug field entirely from `compute_sustainment()` return value.

**Rationale**:
1. **Type Uniformity**: All score-related fields now consistently return `int` (0-100)
2. **Clean API**: Consumers only receive normalized scores, not raw calculations
3. **Backward Compatible**: The `debug` field was not used in production code paths
4. **Simplicity**: No additional complexity or API surface area

### Changes Made

#### 1. `optipanel/chips/aggregate.py:137`
**Before**:
```python
def compute_sustainment(chips_by_tf: dict[str, dict[str, int]] | None) -> dict[str, Any]:
    # ... calculations ...
    return {
        "sustainability": sustainability,  # int
        "fakeout_risk": fakeout_risk,      # int
        "debug": debug,                     # dict with float values ❌
    }
```

**After**:
```python
def compute_sustainment(chips_by_tf: dict[str, dict[str, int]] | None) -> dict[str, int]:
    """Derive sustainability vs fakeout risk from probability chips.

    Bug #34 Fix: Returns only score fields (int) for type consistency.
    All score-related fields in the snapshot now use int (0-100) uniformly.
    Debug/diagnostic data has been removed to eliminate float/int mixing.

    Returns:
        Dictionary with two int scores (0-100):
        - sustainability: Reliability of the current move/signal
        - fakeout_risk: Probability signal is false/will reverse
    """
    # ... calculations ...
    return {
        "sustainability": sustainability,  # int
        "fakeout_risk": fakeout_risk,      # int
    }
```

**Key Changes**:
- Return type changed from `dict[str, Any]` → `dict[str, int]`
- Removed `debug` field and all related code (lines saving to debug dict)
- Updated docstring to document the fix
- Removed fallback `"debug": {}` from empty input case

#### 2. `optipanel/engine/aggregate.py:71`
**Before**:
```python
def build_symbol_snapshot(symbol: str, features: dict[str, Any]) -> dict[str, Any]:
    """
    Pure aggregator that combines battlefield 'units' and setup scores into a single view.

    Returns:
      {
        "symbol": str,
        "units": dict,
        "setups": dict,
        "score": int,
        "advice": "attack" | "defend" | "standby",
        "sustainment": dict,  # sustainability and fakeout_risk scores
      }
    """
```

**After**:
```python
def build_symbol_snapshot(symbol: str, features: dict[str, Any]) -> dict[str, Any]:
    """
    Pure aggregator that combines battlefield 'units' and setup scores into a single view.

    Bug #32 FIX: Updated advice logic to consult exhaustion and sustainability metrics
    before recommending aggressive positions, preventing dangerous trades on overextended
    or unreliable signals.

    Bug #34 FIX: All score-related fields now use consistent int type (0-100 range).
    Removed float values from sustainment to eliminate type ambiguity for API consumers.

    Returns:
      {
        "symbol": str,
        "units": dict[str, dict[str, int]],        # from compute_units(features)
        "setups": dict[str, int],                  # from compute_setups(features)
        "score": int,                              # 0..100 composite
        "advice": "attack" | "defend" | "standby",
        "sustainment": dict[str, int],             # sustainability and fakeout_risk scores (both int)
        "prob_chips": dict[str, dict[str, int]],   # probability chips by timeframe
        "prob_summary": dict[str, dict[str, int]], # summarized chip scores
        "battlefield_bundle": dict[str, float],    # raw market features (not scores)
        "features": dict[str, Any],                # original input features
      }
    """
```

**Key Changes**:
- Added Bug #34 fix note to docstring
- Enhanced type annotations to clearly show all score fields are `int`
- Distinguished between score fields (`int`) and raw data fields (`float`)

## Testing

### New Test Suite: `tests/test_bug_34_type_consistency.py`

Created comprehensive test coverage with 6 test cases:

1. **`test_compute_sustainment_returns_only_ints()`**
   - Validates `compute_sustainment()` returns only `int` values
   - Ensures no `float` contamination in any field
   - Verifies 0-100 range compliance

2. **`test_compute_sustainment_empty_input()`**
   - Tests fallback behavior with `None` input
   - Validates default values are `int`

3. **`test_snapshot_all_scores_are_ints()`**
   - **Comprehensive validation** of entire snapshot structure
   - Checks every score field recursively:
     - `score`: int
     - `setups`: all values int
     - `units`: all nested values int
     - `sustainment`: all values int
     - `prob_chips`: all nested values int
     - `prob_summary`: all nested values int
   - Validates 0-100 range for all scores

4. **`test_snapshot_no_debug_field_in_sustainment()`**
   - Explicitly verifies `debug` field is removed
   - Ensures no nested dicts with float values

5. **`test_snapshot_type_consistency_edge_cases()`**
   - Tests with minimal feature set
   - Recursive float detection to catch any leakage
   - Distinguishes raw data (allowed floats) from scores (must be int)

6. **`test_api_serialization_compatibility()`**
   - Validates JSON serialization works correctly
   - Ensures round-trip serialization maintains types

### Test Results
```bash
$ pytest tests/test_bug_34_type_consistency.py -v

tests/test_bug_34_type_consistency.py::test_compute_sustainment_returns_only_ints PASSED
tests/test_bug_34_type_consistency.py::test_compute_sustainment_empty_input PASSED
tests/test_bug_34_type_consistency.py::test_snapshot_all_scores_are_ints PASSED
tests/test_bug_34_type_consistency.py::test_snapshot_no_debug_field_in_sustainment PASSED
tests/test_bug_34_type_consistency.py::test_snapshot_type_consistency_edge_cases PASSED
tests/test_bug_34_type_consistency.py::test_api_serialization_compatibility PASSED

============================== 6 passed in 1.03s ==============================
```

### Regression Testing
All existing tests continue to pass:
- ✅ `test_aggregate.py` (4 tests)
- ✅ `test_chips_runtime.py` (2 tests)
- ✅ `test_bug_32_advice_logic.py` (17 tests)
- ✅ `test_recon_enrich.py` (3 tests)

**Total**: 32+ tests passing with 100% success rate.

## Impact Analysis

### Breaking Changes
**None**. This is a backward-compatible fix:
- The `debug` field was never used in production code
- `recon/enrich.py:160-163` already stripped out debug when building API responses
- All consuming code only accessed `sustainability` and `fakeout_risk` fields

### Performance Impact
**Positive**: Slight performance improvement:
- Removed unnecessary debug dict allocation
- Reduced memory usage per snapshot
- Smaller payload size for API responses

### API Consumer Impact
**Improved Experience**:
- Uniform type handling: all scores are `int`
- No surprises when parsing responses
- Type checking tools (TypeScript, mypy) will have consistent types
- Simpler JSON schema definition

## Verification

### Manual Verification
You can verify the fix with:

```python
from optipanel.engine.aggregate import build_symbol_snapshot

features = {
    "last": 150.0,
    "dma20": 145.0,
    "support": 140.0,
    "resistance": 155.0,
    "rvol": 1.5,
    "rs_strength": 0.25,
    "vwap_diff": 0.01,
}

snapshot = build_symbol_snapshot("TEST", features)

# All score fields should be int
assert isinstance(snapshot["score"], int)
assert isinstance(snapshot["sustainment"]["sustainability"], int)
assert isinstance(snapshot["sustainment"]["fakeout_risk"], int)
assert "debug" not in snapshot["sustainment"]
print("✅ Bug #34 fix verified!")
```

### Type Signature Verification
```python
from optipanel.chips.aggregate import compute_sustainment

# Before fix: dict[str, Any]
# After fix:  dict[str, int]
result = compute_sustainment(chips_by_tf)
assert all(isinstance(v, int) for v in result.values())
```

## Lessons Learned

### What Went Right
1. **Clear Separation**: Distinguishing score data (`int`) from raw data (`float`) improves API clarity
2. **Comprehensive Testing**: 6 targeted tests catch any future regressions
3. **Zero Breaking Changes**: Careful analysis showed debug field was unused

### Future Prevention
1. **Type Annotations**: Use strict type hints (`dict[str, int]` not `dict[str, Any]`)
2. **Schema Validation**: Consider JSON Schema or Pydantic models for API responses
3. **Test Coverage**: Always validate type consistency in integration tests

### Recommendations
For future development:
1. Consider using `TypedDict` or Pydantic models for snapshot structure
2. Add linting rules to catch `dict[str, Any]` in public APIs
3. Document expected types in API documentation
4. Use `mypy --strict` to catch type inconsistencies

## Related Issues
- **Bug #32**: Fixed advice logic (affects same code)
- **Bug #36**: Systemic use of `float` vs `Decimal` (related type consistency issue)

## References
- Test Suite: `tests/test_bug_34_type_consistency.py`
- Fixed Code: `optipanel/chips/aggregate.py:137`
- Fixed Code: `optipanel/engine/aggregate.py:71`
- Original Bug Report: `ClaudeCloud.md:34`

---

**Fix Verified**: 2025-10-03
**Tests Passing**: 32+ tests, 100% success rate
**Status**: ✅ **PRODUCTION READY**
