# Troubleshooting Guide

This guide lists the most common operational issues and the recommended steps to resolve them.

## CLI Command Fails with Exit Code 2
- **Symptoms:** `sengoku recon` returns exit code 2 with message "IBKR unavailable".
- **Resolution:**
  1. Run `sengoku health --ping` to verify connectivity.
  2. Check IBKR session in TWS/Gateway.
  3. Review logs under `runs/` for `session_error` events.

## No Output in Command Room
- **Symptoms:** `sengoku command-room` shows empty panels.
- **Resolution:**
  1. Ensure watchlists are configured in the profile YAML.
  2. Run `sengoku scan --symbols-json ...` to validate data ingestion.
  3. If running Textual UI, confirm the WebSocket feed is connected.

## Legacy Logger Alert Triggered
- **Symptoms:** Monitoring reports `logger_type="legacy"` metric.
- **Resolution:**
  1. Run `scripts/check_legacy_logger_usage.py --minutes 60` manually.
  2. Identify offending session ID and stack trace in logs.
  3. Replace any direct `SessionLogger` usages with `get_session_logger()`.

## Performance Regression Detected
- **Symptoms:** Benchmarks in `docs/ARCHITECTURE.md` exceeded by >15%.
- **Resolution:**
  1. Execute `scripts/benchmarks/run_benchmarks.py` (available internally) to reproduce locally.
  2. Review recent changes affecting recon/ops loops.
  3. Capture profiling data with `python -m cProfile` on the slow command.

## Web API Returns 500
- **Symptoms:** Planned FastAPI endpoint responds with HTTP 500.
- **Resolution:**
  1. Inspect server logs for stack traces.
  2. Verify request payload matches schema in `docs/API_REFERENCE.md`.
  3. Confirm backend services (IBKR, cache) are operational.

Document additional scenarios as they arise to keep this guide useful for on-call responders.
