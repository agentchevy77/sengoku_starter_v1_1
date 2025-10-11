# Future Expansion Notes

Use this scratchpad to capture larger follow-on ideas that sit beyond the
current WO-UI-WEB-01 scope. Revisit and promote items into real work orders once
we commit to implementing them.

## Security & Access Control
- Add bearer-token or API-key authentication to the FastAPI gateway.
- Introduce request throttling/rate limiting with configurable caps per client.
- Document key rotation and local override workflows for single-operator setups.

## Web Gateway Evolution
- Upgrade FastAPI endpoints to support authenticated websockets/SSE for live
  panel updates.
- Define pagination/filter options for `/watchlist` when we expand beyond the
  prime/secondary lists.

## UI Enhancements
- Integrate richer detail panes (charts, multi-symbol comparisons) once the TUI
  stabilises.
- Consider shared component library for Textual + future web front ends.

## Observability
- Emit structured metrics/logs from both Textual and FastAPI layers for real
  time monitoring.
- Add synthetic tests or health checks that exercise the full stack regularly.

## Configuration & Data Contracts
- Extend Pydantic validation to TWS payloads, alert envelopes, and feature bundles to eliminate implicit dict assumptions.
- Introduce typed factories/helpers so downstream components consume Pydantic models directly (reduces coercion defects).
- Document configuration override precedence (file vs env vs secrets) now that validation happens centrally. 

_Keep this file terse; as ideas firm up, promote them to proper work orders with
allowed paths and definition of done._
