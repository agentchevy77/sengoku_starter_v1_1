# Error Codes and Meanings

The Sengoku Decision Cockpit uses consistent exit codes and error identifiers across CLI commands, services, and monitoring scripts. This guide documents the most common values.

## Process Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| `0` | Success | No action required. |
| `1` | Recoverable error (invalid input, no data) | Fix input and retry. |
| `2` | Operational issue (external dependency unavailable) | Check IBKR connectivity, cache services, or network. |
| `3` | Configuration error (missing env vars, secrets) | Correct configuration and redeploy. |
| `4` | Internal bug (uncaught exception) | Escalate to engineering with logs and session ID. |

## Session Logger Error Types

| Error Type | Trigger | Notes |
|------------|--------|-------|
| `operation_failed` | Exception inside `operation_context`. | Includes symbol/name context. |
| `session_error` | Unhandled exception at session boundary. | Session status becomes `error`. |
| `emit_failure` | Downstream logging error. | Logger writes to stderr fallback. |

## Monitoring Alerts

| Metric | Condition | Mitigation |
|--------|-----------|------------|
| `logger_type="legacy"` | Legacy logger detected. | Run `scripts/check_legacy_logger_usage.py` and migrate offending code. |
| `watchlists_render_backoff` | Watchlist renders occurring in backoff. | Investigate scheduler usage/budgets. |

Keep this document updated whenever new exit codes or error identifiers are introduced. Tests asserting documentation presence will fail if the file is missing.
