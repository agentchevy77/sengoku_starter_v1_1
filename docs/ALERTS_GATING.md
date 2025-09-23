# Alerts Gating (Acceptance × Readiness)

Each alert may include a `gate` object:

```json
{
  "kind": "trend_long",
  "symbol": "AAPL",
  "threshold": 70,
  "value": 86,
  "gate": {
    "accepted": true,
    "readiness": 78,
    "state": "go"
  }
}
```

## CLI toggles & env overrides

- `--require-acceptance` or `SENGOKU_NOTIFY_REQUIRE_ACCEPT=1` drops alerts whose gate state is not `go`.
- `--ready-min INT` or `SENGOKU_NOTIFY_READY_MIN=65` sets the readiness threshold used for `go` gating.

## Payload extras

- Each alert now carries a `readiness` block with `attack`, `defense`, and source components (`attack_core`, `defense_core`, `sustainability`, `fakeout_risk`, `acceptance`).
