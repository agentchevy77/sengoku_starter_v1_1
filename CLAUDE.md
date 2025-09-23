# Claude Assistant Instructions for Sengoku Project

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

*Last Updated: 2025-09-23*
*Remember: `get_session_logger()` is the only supported logger path—use it everywhere!*
