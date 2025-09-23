# Enhanced Session Logging

## Overview

The enhanced session logging system provides comprehensive tracking and monitoring of Sengoku operations with minimal changes to existing code. It extends the base `EventLogger` class while maintaining full backward compatibility.

## Key Features

### 1. Session Tracking
- Automatic unique session ID generation
- Session lifecycle events (start, end, error)
- Session metadata tracking (duration, command, parameters)

### 2. Structured Event Logging
- Operation tracking with automatic timing
- Error logging with full context and stack traces
- Metric emission for performance monitoring
- Context stacking for nested operations

### 3. Log Management
- Automatic log rotation based on size and age
- Compression support for archived logs
- Configurable retention policies

## Usage Examples

### Basic Session Logging

```python
from optipanel.ops.session_logger import get_session_logger

# Simple usage with context manager
with get_session_logger(command="my_operation") as logger:
    logger.emit("event", {"data": "value"})
    logger.emit_metric("latency", 95.5, unit="ms")
```

### Operation Tracking

```python
from optipanel.ops.session_logger import SessionLogger

logger = SessionLogger(command="batch_process")

# Automatic timing and context tracking
with logger.operation_context("fetch_data", source="api"):
    # Your operation code here
    data = fetch_from_api()
    logger.emit("data_fetched", {"count": len(data)})

# Metrics are automatically collected
logger.finalize()
```

### Error Handling

```python
logger = SessionLogger(command="risky_operation")

try:
    perform_risky_operation()
except Exception as e:
    logger.emit_error(
        "operation_failed",
        "Failed to complete operation",
        details={"context": "important_data"},
        exception=e
    )
    raise
```

### Enhanced Ops Loop Integration

```python
from optipanel.ops.ops_loop_enhanced import ops_loop_enhanced

# Drop-in replacement with session logging
result = ops_loop_enhanced(
    provider,
    profile,
    ticks=10,
    sleep=1.0,
    width=24,
    top_n=2,
    session_id="custom-session-123"  # Optional
)

# Result includes session_id for correlation
print(f"Session: {result['session_id']}")
print(f"Total alerts: {result['total_alerts']}")
```

## Configuration

### Environment Variables

- `SENGOKU_LOG_DIR`: Directory for log files (default: `./runs`)
- `SENGOKU_LOG_LEVEL`: Logging level (default: `INFO`)
- `SENGOKU_MAX_LOG_FILES`: Maximum number of session log files to keep

### Log Rotation Settings

```python
from optipanel.ops.session_logger import LogRotationManager

manager = LogRotationManager(
    log_dir="./logs",
    max_size_mb=100,      # Rotate files larger than 100MB
    max_age_days=30,      # Delete files older than 30 days
    max_files=100         # Keep maximum 100 log files
)

# Run rotation and cleanup
result = manager.manage()
print(f"Rotated: {result['rotated']}")
print(f"Removed: {result['removed']}")
```

## Log File Format

Logs are written in JSONL format (one JSON object per line) to files named `events-YYYYMMDD.jsonl`:

```json
{
  "ts": 1734567890.123,
  "kind": "operation",
  "session_id": "1734567890123-abc123",
  "command": "ops_loop",
  "operation": "fetch_data",
  "details": {"symbol": "AAPL"},
  "duration_ms": 95.5
}
```

## Migration from EventLogger

`get_session_logger()` now returns the hardened `SafeSessionLogger`, providing
the same API as `EventLogger` plus session metadata, metrics, and lifecycle
events.

```python
# Before
from optipanel.ops.eventlog import EventLogger
logger = EventLogger()
logger.emit("event", {"data": "value"})

# After (safer and richer)
from optipanel.ops.session_logger import get_session_logger

with get_session_logger(command="my_command") as logger:
    logger.emit("event", {"data": "value"})
    logger.emit_metric("cache_hits", 42)
```

!!! note
    The legacy `SessionLogger` implementation has been removed. All call sites
    must use `get_session_logger()` (which returns `SafeSessionLogger`).

To catch any unexpected regressions, run
`scripts/check_legacy_logger_usage.py` in monitoring. It scans recent logs for
`logger_type="legacy"` metrics — a value that should now never appear — and
exits non-zero if one is found. See `docs/monitoring/legacy_logger_alert.md`
for integration examples (Nagios, Grafana, systemd timers).

## Best Practices

1. **Use context managers** for automatic session finalization
2. **Track operations** with `operation_context` for timing metrics
3. **Log errors with context** using `emit_error` with exception details
4. **Emit metrics** for key performance indicators
5. **Set up log rotation** to prevent disk space issues
6. **Use session IDs** for correlating events across distributed systems

## Monitoring and Analysis

Session logs can be analyzed to:
- Track operation performance over time
- Identify error patterns and frequencies
- Monitor system health and throughput
- Debug issues with full context
- Generate operational reports

Use tools like `jq` for command-line analysis:

```bash
# Count events by kind
cat runs/events-*.jsonl | jq -r '.kind' | sort | uniq -c

# Find slow operations
cat runs/events-*.jsonl | jq 'select(.kind=="operation" and .duration_ms > 1000)'

# Track error rates by session
cat runs/events-*.jsonl | jq -r 'select(.kind=="error") | .session_id' | sort | uniq -c
```
