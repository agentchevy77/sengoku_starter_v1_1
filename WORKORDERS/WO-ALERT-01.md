# WO-ALERT-01 — Alerts engine (pure, no I/O)

Allowed paths:
- optipanel/alerts/__init__.py
- optipanel/alerts/engine.py

Implement DEFAULT_THRESH, gen_alerts(snapshot, thresholds=None), analyze_batch(snapshots, thresholds=None).
Rules:
- Score alerts: score >= score_attack -> "score_attack"; score <= score_defend -> "score_defend".
- Setup alerts: fire when value >= threshold for
  ["breakout_up","breakdown_down","bounce_up","rejection_down","trend_long","trend_short","exhaustion"].
- Severity: high if value >= threshold+15; medium if >= threshold+5; else low.
- Message: "SYMBOL kind value >= threshold" (or "<= threshold" for score_defend).

**Primary test:** `pytest tests/test_alerts.py -q`
