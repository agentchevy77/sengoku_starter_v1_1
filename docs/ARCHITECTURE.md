# Sengoku Decision Cockpit – Architecture Overview

## High-Level View

```mermaid
graph TD
    subgraph Adapters
        IBKR[IBKR Providers]
        Cache[Cache Services]
    end

    subgraph Runtime
        Scheduler[Scheduler]
        Loop[Ops Loop]
        Health[Health Checks]
    end

    subgraph Engines
        Recon[Recon Engine]
        Alerts[Alerts Engine]
        Notify[Notify Engine]
    end

    subgraph Interfaces
        CLI[CLI]
        TUI[Textual (Planned)]
        API[FastAPI Service (Planned)]
    end

    IBKR --> Scheduler
    Cache --> Scheduler
    Scheduler --> Loop
    Loop --> Engines
    Engines --> CLI
    Engines --> TUI
    Engines --> API
```

## Layer Responsibilities

| Layer | Responsibilities | Key Modules |
|-------|------------------|-------------|
| Interfaces | Present data to operators via CLI/TUI/API. Handle command dispatch and routing. | `optipanel/cli`, `scripts/tui_*` (planned), `fastapi` (planned) |
| Engines | Domain logic for recon, alerts, notify, readiness. Stateless, pure computations where possible. | `optipanel/recon`, `optipanel/alerts`, `optipanel/notify`, `optipanel/readiness` |
| Runtime | Long-running processes, schedulers, orchestration, health monitoring. | `optipanel/runtime`, `optipanel/ops/ops_loop(_enhanced)` |
| Adapters | External integrations (IBKR), caching, persistence, environment helpers. | `optipanel/adapters`, `optipanel/services/cache` |
| Shared Infrastructure | Logging, metrics, settings, dependency injection. | `optipanel/ops/session_logger`, `optipanel/obs` |

## Data Flow

1. **Market Data** – IBKR adapters fetch data and expose `FeaturesProvider` protocols.
2. **Runtime Orchestration** – The ops loop schedules which watchlists to process and requests features.
3. **Engines** – Recon/Alerts/Readiness calculate signals and recommendations.
4. **Presentation** – CLI/TUI/API render the aggregated signals. Textual UI will subscribe to the same view models used by the CLI, while the upcoming FastAPI layer will expose them over HTTP/WebSockets.
5. **Telemetry** – `SafeSessionLogger` records session start/end, metrics, and errors. `scripts/check_legacy_logger_usage.py` and `scripts/metrics/watchlist_dashboard.py` surface these events to monitoring.

## Session Logging Contract

All interactive surfaces **must** instantiate loggers via `get_session_logger()`. The helper returns a `SafeSessionLogger` that enforces:

- Thread-safe writes
- Bounded metrics storage
- Structured error payloads
- Identity via `session_id`

Production processes wrap long-running loops with `ensure_safe_logger()` to assert that the safe implementation is always used.

## Testing Strategy

- **Unit Tests** – Located under `tests/`, cover engines, adapters, and infrastructure. `tests/test_session_logger.py` enforces behaviour of the safe logger.
- **Integration Points** – `scripts/test_logger_safety.py` and `test_full_system.sh` exercise end-to-end flows.
- **Docstring Coverage** – `tests/test_docstring_regression.py` (introduced in this change) ensures critical modules remain documented.

## Future Enhancements

- **Textual UI** – Replace ASCII output with reactive panels that consume the same view models.
- **FastAPI Layer** – Expose recon/command-room data via REST/WebSockets for dashboards and desktop wrappers.
- **Dashboard Metrics** – Use `scripts/metrics/watchlist_dashboard.py` to feed Prometheus/Grafana with watchlist telemetry.

## Performance Benchmarks

| Scenario | Environment | Metric | Baseline |
|----------|-------------|--------|----------|
| Recon batch (50 symbols) | Ubuntu 22.04, Python 3.12 | Runtime | 820 ms |
| Ops loop tick (3 watchlists) | Same as above | Runtime | 1.4 s |
| Session log throughput | Local SSD, JSONL writer | Events/sec | 4,800 |
| IBKR fetch retry budget | Live demo account | Max retries | 3 before backoff |

Measurements are captured with `scripts/benchmarks/run_benchmarks.py` (see troubleshooting guide). Record updated baselines whenever major performance-affecting changes land. Deviations >15% should trigger an investigation.
