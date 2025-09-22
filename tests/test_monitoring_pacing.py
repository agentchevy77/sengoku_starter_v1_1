from optipanel.monitoring import evaluate_pacing_alerts, load_thresholds_from_env


def test_evaluate_pacing_alerts_warn_and_crit():
    metrics = {
        "global_rate_max_requests": 40,
        "global_rate_interval_sec": 60.0,
        "global_rate_last_wait_sec": 3.5,
        "global_rate_total_wait_sec": 25.0,
    }

    alerts = evaluate_pacing_alerts(metrics)
    severities = {a.severity for a in alerts}
    assert "high" in severities
    assert any(a.last_wait_sec >= 3.5 for a in alerts)


def test_evaluate_pacing_alerts_handles_missing_values():
    metrics = {"global_rate_max_requests": 0}
    alerts = evaluate_pacing_alerts(metrics)
    assert alerts == []


def test_load_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("SENGOKU_TWS_PACING_LAST_WAIT_WARN", "5.5")
    overrides = load_thresholds_from_env()
    assert overrides["last_wait_warn"] == 5.5

    metrics = {
        "global_rate_max_requests": 40,
        "global_rate_interval_sec": 60.0,
        "global_rate_last_wait_sec": 3.0,
        "global_rate_total_wait_sec": 30.0,
    }

    alerts = evaluate_pacing_alerts(metrics, thresholds=overrides)
    assert alerts  # ratio alert still triggered
    assert all(a.last_wait_sec >= 3.0 for a in alerts)
