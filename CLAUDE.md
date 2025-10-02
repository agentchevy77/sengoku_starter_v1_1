# Claude Assistant Instructions for Sengoku Project

## Recent Changes

### 2025-10-02: SetupConfig Refactoring (commit 66fa459)
**Status**: ✅ **COMPLETE**

Extracted 60+ hardcoded magic numbers into centralized `SetupConfig` dataclass:
- **Problem**: Hardcoded thresholds (0.01, 85.0, etc.) scattered throughout compute_setups()
- **Impact**: Hard to read, maintain, and test different configurations
- **Solution**: Created `SetupConfig` dataclass with 87 named parameters
- **Backward Compatibility**: 100% compatible - config parameter is optional
- **Testing**: 13/13 tests pass, including 6 characterization tests proving mathematical equivalence
- **Coverage**: 97% (153/158 lines)
- **Files**: `optipanel/setups/engine.py`, `tests/test_setups_engine_refactor.py`

This completes the SetupConfig refactoring from Rebuild1.md Phase 1.

### 2025-10-02: TWS Error Handler Signature Fix (commit ce3b6e9)
**Status**: ✅ **COMPLETE**

Fixed critical stability bug in `RealTwsFetcher` where error handler signature was incompatible with ibapi 10.37.2:
- **Problem**: `_BaseApp.error()` expected 4-5 args, ibapi 10.37.2 sends 6 args
- **Symptom**: `TypeError` exceptions in background thread during TWS error handling
- **Fix**: Updated signature to `error(self, reqId: int, errorTime: int, errorCode: int, errorString: str, advancedOrderRejectJson="")`
- **Impact**: No more thread exceptions; TWS fetcher now fully stable
- **Testing**: All TWS tests pass (3/3), production validation successful
- **File**: `optipanel/adapters/ibkr/tws_fetcher.py:99-116`

This was the first of three surgical fixes recommended by third-party analysis to stabilize the V1 implementation.

---

## Session Logging Requirements

**IMPORTANT**: This project uses an enhanced session logging system. When implementing new features or modifying existing code, follow these guidelines:

### Always Use get_session_logger for New Code

```python
# For new operations, ALWAYS use:
from optipanel.ops.session_logger import get_session_logger

with get_session_logger(command="operation_name") as logger:
    # Your code here
    logger.emit("event", {"data": value})
```

### Key Components to Remember

1. **Primary Logger**: `SafeSessionLogger` via `get_session_logger`
   - Hardened against concurrency, serialization, and rotation issues
   - Drop-in replacement for `EventLogger` data consumers
   - This is the only supported implementation; the legacy class has been removed
   - Safe instances emit a `logger_type="safe"` metric for observability

2. **Factory Function**: `get_session_logger()`
   - Preferred way to create loggers
   - Automatically uses SENGOKU_LOG_DIR environment variable

3. **Operation Tracking**: Always wrap significant operations
   ```python
   with logger.operation_context("operation_name", **context):
       # Operation code
   ```

4. **Error Logging**: Use structured error logging
   ```python
   logger.emit_error("error_type", "message", details={...}, exception=e)
   ```

### Integration Points

- **CLI Commands**: All commands in `optipanel/cli/main.py` should use SessionLogger
- **Ops Loops**: Use `ops_loop_enhanced` from `optipanel.ops.ops_loop_enhanced`
- **Runtime Operations**: Wrap with operation_context for timing
- **Alerts/Recon**: Log decisions with full context

### Testing Requirements

- Run tests with: `python3 -m pytest tests/test_session_logger.py -v`
- Verify backward compatibility: `python3 -m pytest tests/test_eventlog.py -v`
- Test demo: `python3 -m scripts.session_logger_demo`

### Environment Variables

- `SENGOKU_LOG_DIR`: Log directory (default: ./runs)
- `SENGOKU_LOG_LEVEL`: Logging level (default: INFO)
- `SENGOKU_MAX_LOG_FILES`: Retention limit for session logs
- `scripts/check_legacy_logger_usage.py`: Add to cron/Grafana to alert if any
  `logger_type="legacy"` metrics appear in recent logs

### Log Analysis Commands

```bash
# View today's events
cat runs/events-$(date +%Y%m%d).jsonl | jq '.'

# Count events by type
cat runs/events-*.jsonl | jq -r '.kind' | sort | uniq -c

# Find errors
cat runs/events-*.jsonl | jq 'select(.kind=="error")'

# Track slow operations
cat runs/events-*.jsonl | jq 'select(.duration_ms > 1000)'
```

## Development Principles

1. **Preserve Backward Compatibility**: Never break existing EventLogger usage
2. **Add Context**: Always include session_id and operation context
3. **Track Performance**: Use operation_context for timing
4. **Log Errors Properly**: Include stack traces and context
5. **Clean Up Logs**: Run LogRotationManager periodically
6. **Avoid direct EventLogger usage**: stick with `get_session_logger()` so the hardened path is used consistently

## Quick Reference

```python
# Import
from optipanel.ops.session_logger import get_session_logger

# Basic usage (context manager finalizes automatically)
with get_session_logger(command="my_command") as logger:
    with logger.operation_context("fetch", symbol="AAPL"):
        # code here
        pass
    logger.emit_metric("cache_hits", 42)

# Error handling
try:
    risky_operation()
except Exception as e:
    logger.emit_error("op_failed", "Description", exception=e)
    raise

```

## File Locations

- Implementation: `optipanel/ops/session_logger.py`
- Tests: `tests/test_session_logger.py`
- Demo: `scripts/session_logger_demo.py`
- Docs: `docs/session_logging.md`
- Enhanced Ops: `optipanel/ops/ops_loop_enhanced.py`

---

## Rebuild Documents (Unimplemented Proposals)

**CRITICAL CONTEXT**: The files `Rebuild1.md` and `Rebuild2.md` are **research and proposal documents** that were NOT implemented in the codebase. They are kept for reference and lessons learned, but the code changes described in them were not committed due to the large scope of changes.

### What Was Proposed But NOT Implemented:

#### From Rebuild1.md (Phase 1 Bug Fixes):
- Cache race condition fixes in `_TickCache._prune_expired`
- TWS fetcher thread leak fixes in `RealTwsFetcher._connect`
- Unsafe type conversion fixes in CLI using `safe_int()`
- **`SetupConfig` refactoring** in `optipanel/setups/engine.py` (see below)

#### From Rebuild1.md (Phase 2 - AsyncTwsFetcher v2):
- New `AsyncTwsFetcher` with async architecture
- Self-healing connection management
- Result objects for partial failure handling

#### From Rebuild2.md (After-Action on v2):
- Analysis revealed v2 AsyncTwsFetcher was unstable (hangs, timeouts)
- Discovery of `ib_insync` vs `ibapi` dependency mismatch
- Proposed `TwsFetcherV3` ("Sledgehammer") - stateless connect-fetch-disconnect pattern
- Dependency manifest corrections

### Current Codebase State:

**The current codebase has:**
- Original `TwsFetcher` implementation (production)
- ✅ Refactored `SetupConfig` in `optipanel/setups/engine.py` (completed 2025-10-01)
- Experimental `TwsFetcherV3` awaiting validation (not integrated)
- `ibapi 10.37.2` in `.venv` (up-to-date)

### The SetupConfig Refactoring (COMPLETED 2025-10-02, commit 66fa459)

**Problem**: `optipanel/setups/engine.py` originally contained dozens of hardcoded numeric thresholds (e.g., `0.01`, `85.0`, `60.0`, `1.2`, `0.1`) that made the code:
- Hard to read (no context for what numbers mean)
- Hard to maintain (must hunt for values to change)
- Inflexible (cannot test different threshold configurations)

**Solution Implemented**: Introduced a `SetupConfig` dataclass to encapsulate all 60+ model parameters:

```python
@dataclass
class SetupConfig:
    """Configuration for the Battlefield Scoring Engine.

    These parameters define the quantitative model used to score various
    trading setups. Each threshold and multiplier has been tuned and should
    be treated as part of the model specification.
    """
    # Breakout Up thresholds
    breakout_up_gap_max: float = 0.01
    breakout_up_base_near: float = 60.0
    breakout_up_base_far: float = 30.0
    breakout_up_base_broken: float = 85.0
    # ... (60+ parameters total for all setup types)

def compute_setups(features: dict[str, Any], config: SetupConfig | None = None) -> dict[str, int]:
    if config is None:
        config = SetupConfig()
    # Uses config parameters instead of hardcoded values
```

**Implementation Details**:
- Test-driven approach using characterization tests (golden master pattern)
- 6 test scenarios verify mathematical equivalence with original implementation
- All tests pass (11/11) - refactoring proven to preserve exact behavior
- Backward compatible - existing code unchanged (config defaults to original values)

**Files Modified**:
- `optipanel/setups/engine.py` - Added SetupConfig, refactored compute_setups()
- `tests/test_setups_engine_refactor.py` - Characterization tests

**Status**: ✅ **COMPLETE** - Committed 2025-10-02 (commit 66fa459)
- 13/13 tests pass (6 characterization + 7 original)
- 97% test coverage
- 100% backward compatible
- Black/ruff formatting passes

---

## TwsFetcherV3 Validation Status

**Status**: ❌ **ABANDONED - Third-Party Analysis Correct**

### Historical Context (2025-10-01):

Following the third-party opinion's recommendations, we have implemented TwsFetcherV3 ("The Sledgehammer") **in isolation** for validation purposes:

**Files Created**:
1. `optipanel/adapters/ibkr/tws_fetcher_v3.py` - Stateless fetcher implementation
2. `scripts/validate_v3_fetcher.py` - Comprehensive 6-test validation suite
3. `docs/tws_fetcher_v3_validation.md` - Complete validation guide

**Key Improvements Over Rebuild2.md Proposal**:
- ✅ Uses `ibapi` (current dependency) instead of `ib_insync` (avoids dependency issues)
- ✅ Comprehensive error handling and diagnostics
- ✅ Performance benchmarking built-in
- ✅ Detailed logging and observability
- ✅ 6-test validation suite with clear pass/fail criteria

### What We Learned:

**Python Environment**: `.venv` with `ibapi 10.37.2` (verified 2025-10-01)
- ⚠️ System Python has outdated `ibapi 9.81.1` - DO NOT USE
- ✅ Always use `.venv/bin/python3` for all scripts

**Testing Revealed**:
- Both original and V3 implementations failed with same connection errors
- Root cause: TWS API configuration issue, not code quality
- Original `RealTwsFetcher` has proven architecture
- V3 "Sledgehammer" offers no advantages over fixing original bugs

### Final Decision (2025-10-02):

**Third-Party Analysis Was 100% Correct:**

After attempting validation, we discovered:

1. **TWS Connectivity CONFIRMED WORKING** (2025-10-02)
   - ✅ TCP connection: SUCCESS at `192.168.80.1:7496`
   - ✅ API handshake: SUCCESS with client ID 777
   - ✅ Original `RealTwsFetcher`: **WORKING** - Successfully fetches data
   - ❌ New `TwsFetcherV3`: Times out waiting for historical data (30s timeout)
   - **Conclusion**: Connection works, original fetcher works, V3 has data retrieval issues

2. **V3 Was a Failed Experiment**
   - TwsFetcherV3 is a research proposal from Rebuild2.md
   - AsyncTwsFetcher V2 was the actual failed implementation that broke stability
   - The original `RealTwsFetcher` is still the production code
   - Original fetcher successfully retrieves data; V3 does not

3. **The Correct Path Forward**
   - ✅ Keep using `RealTwsFetcher` (proven, stable architecture - **CONFIRMED WORKING**)
   - ✅ Apply targeted bug fixes from Rebuild1.md (cache race conditions, thread leaks, error handler signature)
   - ❌ Do NOT attempt V2 or V3 replacement (failed experiments)
   - ❌ Do NOT integrate TwsFetcherV3 into production

### Working TWS Configuration (2025-10-02):

```bash
# Confirmed working configuration
SENGOKU_TWS_HOST=192.168.80.1
SENGOKU_TWS_PORT=7496
SENGOKU_TWS_CLIENT_ID=777

# Test command
SENGOKU_TWS_HOST=192.168.80.1 SENGOKU_TWS_PORT=7496 SENGOKU_TWS_CLIENT_ID=777 .venv/bin/python3 scripts/test_original_fetcher.py
```

**Test Results** (verified multiple times 2025-10-02):
- ✅ Connection: SUCCESS (~6-7s to connect)
- ✅ Data fetch: SUCCESS (returns feature dictionary)
- ⚠️ Known issue: Thread exception in error handler (signature mismatch - bug to fix)

**V3 vs V1 Comparison**:
- Both V3 and V1 connect successfully and send historical data requests
- V1 receives data back from TWS (even if all zeros when market closed)
- V3 times out after 30s waiting for TWS response - never receives data
- Root cause: V3 has a fundamental data retrieval/response handling issue
- **Conclusion**: V3 is not viable; stick with V1 and apply bug fixes

### Files to Keep (Reference Only):

These files document the V3 experiment but should NOT be integrated:
- `optipanel/adapters/ibkr/tws_fetcher_v3.py` - Research implementation
- `scripts/validate_v3_fetcher.py` - Validation suite (never completed)
- `scripts/tws_connection_test.py` - Diagnostic tool (useful for debugging)
- `scripts/test_original_fetcher.py` - Test for production fetcher
- `docs/tws_fetcher_v3_validation.md` - Historical documentation

### Production Fetcher:

**Active Implementation**: `optipanel/adapters/ibkr/tws_fetcher.py` (`RealTwsFetcher`)
- Main method: `features_for_symbols(symbols: list[str]) -> dict[str, dict[str, Any]]`
- Uses `ibapi 10.37.2` in `.venv` (verified working)
- Connection pattern: Persistent connection with background thread
- Status: **Stable** (when TWS API is properly configured)

**Stability Fixes Applied**:
1. ✅ **Error handler signature mismatch** - **FIXED** (2025-10-02, commit ce3b6e9)
   - Updated `_BaseApp.error()` signature to match ibapi 10.37.2
   - Added `errorTime` parameter, renamed `code`→`errorCode`, `msg`→`errorString`
   - Added type hints and comprehensive docstring
   - **Result**: No more TypeError exceptions in background thread
   - **Validation**: All TWS tests pass, production fetching works perfectly

**Remaining Bugs to Fix** (from Rebuild1.md):
1. ⏳ Cache race conditions in `_TickCache._prune_expired` (not in TWS fetcher - in API cache)
2. ⏳ Thread leaks in `RealTwsFetcher._connect` method
3. ⏳ Potential improvements to error handling and connection management

**Next Steps**: Apply remaining surgical fixes to `RealTwsFetcher` as needed.

---

*Last Updated: 2025-10-02*
*Remember: `get_session_logger()` is the only supported logger path—use it everywhere!*