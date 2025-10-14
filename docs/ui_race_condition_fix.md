# Textual UI Race Condition Fix Documentation

## Overview
This document describes the comprehensive fix applied to resolve critical race conditions and related issues in the Textual UI refresh logic (Issues #14, #15, #16, #17).

## Issues Addressed

### Issue #14: Critical Race Condition in UI Refresh Logic (HIGH)
**Problem**: Non-atomic check-then-act pattern allowed multiple concurrent refresh tasks.

### Issue #15: Stale UI Updates from Orphaned Tasks (HIGH)
**Problem**: Orphaned tasks would complete after newer tasks, overwriting fresh data with stale data.

### Issue #16: Permanent UI Freeze on Backend Deadlock (CRITICAL)
**Problem**: No timeout on backend calls could cause permanent UI freeze.

### Issue #17: Unhandled Exception on Shutdown (LOW)
**Problem**: Only `CancelledError` was suppressed during shutdown, not other exceptions.

## Solution Architecture

### 1. Atomic Task Management
- Added `asyncio.Lock` (`_refresh_lock`) to ensure atomic check-then-act operations
- All task creation and cancellation happens within the lock's critical section
- Prevents race conditions between timer-triggered and user-triggered refreshes

### 2. Generation Tracking
- Added `_refresh_generation` counter that increments with each new refresh
- Tasks check their generation before updating UI
- Stale generations are silently discarded, preventing orphaned tasks from updating UI

### 3. Timeout Protection
- Wrapped `run_tick` backend call in `asyncio.wait_for` with 30-second timeout
- Prevents permanent UI freeze if backend deadlocks
- Shows clear error message on timeout

### 4. Robust Shutdown
- Changed from suppressing only `CancelledError` to suppressing all exceptions
- Ensures clean shutdown even if task cleanup fails

## Implementation Details

### Key Components Added

```python
# In __init__:
self._refresh_lock: asyncio.Lock = asyncio.Lock()  # Atomic operations
self._refresh_generation: int = 0                   # Track task generations

# New async scheduling method:
async def _schedule_refresh_async(self, force: bool = False):
    async with self._refresh_lock:  # ATOMIC SECTION
        # Check and cancel old task if needed
        # Increment generation
        # Create new task

# Enhanced refresh with generation checking:
async def _refresh_once_with_generation(self, generation: int):
    # Perform refresh with timeout
    result = await asyncio.wait_for(..., timeout=30.0)

    # Only update UI if we're still current generation
    if generation == self._refresh_generation:
        pane.display(panel_text)
```

### Race Condition Timeline (Before Fix)
```
T0: Timer triggers _schedule_refresh()
T1: Timer checks _inflight.done() → True
T2: User presses 'R', triggers _schedule_refresh(force=True)
T3: User's call checks _inflight.done() → True
T4: Timer creates task, assigns to self._inflight
T5: User creates task, overwrites self._inflight ← RACE CONDITION!
T6: Timer's task becomes orphaned but continues running
T7: User's task completes, updates UI with fresh data
T8: Timer's task completes, overwrites with stale data ← BUG!
```

### Protected Timeline (After Fix)
```
T0: Timer triggers _schedule_refresh()
T1: Timer acquires lock, checks, creates task, releases lock
T2: User presses 'R', triggers _schedule_refresh(force=True)
T3: User waits for lock...
T4: User acquires lock, sees task in progress
T5: User cancels old task (force=True), creates new task
T6: Old task's generation != current, update skipped
T7: New task updates UI with correct generation
```

## Testing

### Test Coverage
- `test_race_condition_exists_in_original`: Demonstrates original race condition
- `test_orphaned_task_scenario`: Shows how tasks become orphaned
- `test_concurrent_refresh_calls_stress_test`: Stress test with many concurrent calls
- `test_check_then_act_pattern_fixed`: Verifies all fixes are in place
- `test_fix_with_asyncio_lock`: Demonstrates lock-based solution
- `test_generation_prevents_stale_updates`: Verifies generation tracking

### Running Tests
```bash
python3 -m pytest tests/test_textual_race_condition.py -v -s
```

Note: Some tests require the `textual` module. The verification tests can run without it.

## Performance Impact
- **Minimal**: Lock is only held during task scheduling (microseconds)
- **No impact on refresh rate**: Backend operations happen outside lock
- **Memory**: Negligible (one lock object + integer counter)

## Backward Compatibility
- Fully backward compatible
- Legacy `_refresh_once()` method retained, delegates to new implementation
- No changes to public API or behavior

## Files Modified
- `optipanel/ui/textual/minimal.py`: Complete fix implementation
- `tests/test_textual_race_condition.py`: Comprehensive test suite

## Verification
After applying the fix:
1. Race conditions are impossible due to atomic operations
2. Stale updates cannot occur due to generation checking
3. UI cannot permanently freeze due to timeout
4. Shutdown is clean regardless of exceptions

## Future Considerations
- Consider making timeout configurable (currently hardcoded to 30s)
- Could add metrics/logging for refresh performance monitoring
- Generation counter could wrap after 2^63 refreshes (not a practical concern)