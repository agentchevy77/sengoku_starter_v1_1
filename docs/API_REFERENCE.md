# Public Interfaces Reference

This document captures the interfaces that external automation or interactive operators may rely upon. It will evolve alongside the upcoming FastAPI service. For now, it focuses on the stable command-line entry points and planned HTTP endpoints.

## Command-Line Interfaces

| Command | Description | Primary Output |
|---------|-------------|----------------|
| `sengoku recon` | Generate recon readiness data for specified symbols. | JSON or ASCII table. |
| `sengoku alerts` | Emit alert payloads using the alerts engine. | JSON list of alerts. |
| `sengoku health` | Produce runtime and IBKR health snapshots. | JSON health document. |
| `sengoku command-room` | Render the command room battlefield for watchlists. | ASCII (Textual UI planned). |

All commands support `--help` for option details. Exit codes follow the conventions documented in `ERROR_CODES.md`.

## Planned REST API (FastAPI)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/recon?symbols=AAPL,MSFT` | Fetch recon metrics for the requested symbols. | JSON document matching CLI recon output. |
| `GET` | `/api/v1/command-room?profile=prime` | Retrieve the latest command-room view. | JSON with panels and alerts. |
| `GET` | `/api/v1/health` | Current runtime + IBKR health snapshot. | JSON health payload. |
| `WS` | `/ws/stream` | Streaming updates (alerts, recon deltas). | JSON event stream. |

Authentication and rate limiting are handled via API keys (to be implemented alongside the FastAPI service). Clients must tolerate reconnection and backoff behaviour.

## Python Modules (Stable APIs)

| Module | Purpose | Key Objects |
|--------|---------|-------------|
| `optipanel.recon.enrich` | Recon calculation pipeline. | `build_recon_entry`, `enrich_alerts_with_gate`. |
| `optipanel.ops.session_logger` | Safe session logging factory. | `get_session_logger`, `ensure_safe_logger`. |
| `optipanel.runtime.loop` | Pure tick runner for local simulations. | `run_once`, `run_once_with`. |

These modules are considered public for internal usage. Backwards incompatible changes must be versioned in `CHANGELOG.md`.
