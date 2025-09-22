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
