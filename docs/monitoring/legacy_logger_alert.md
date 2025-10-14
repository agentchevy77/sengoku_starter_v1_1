# Legacy Logger Alert Wiring

This repository now emits a `metric` event with `metric="logger_type"` every time
`get_session_logger()` creates a new logger. The value is `safe` for healthy
invocations. Any appearance of `value="legacy"` indicates a regression and should
raise an operational alarm.

Use `scripts/check_legacy_logger_usage.py` to automate the check. The script
scans recent `events-*.jsonl` files and exits with status `1` when a legacy
metric is discovered.

## Cron / Nagios example

Add the following command definition and service to Nagios (or Icinga):

```
define command{
    command_name    check_legacy_logger
    command_line    /usr/bin/env python3 /opt/sengoku/scripts/check_legacy_logger_usage.py --minutes 15 --quiet
}

define service{
    host_name               sengoku-prod
    service_description     Legacy Logger Usage
    check_command           check_legacy_logger
    check_interval          5
    retry_interval          1
}
```

For a simple cron-based alert (mail on failure):

```
*/5 * * * * /usr/bin/env python3 /opt/sengoku/scripts/check_legacy_logger_usage.py --minutes 30 --quiet || mail -s "[sengoku] legacy logger detected" ops@example.com < /dev/null
```

## Grafana Loki / Promtail example

If you stream JSONL events into Loki, create a recording rule that counts legacy
metrics:

```
record: sengoku:legacy_logger_events:rate5m
expr: sum(rate({app="sengoku", kind="metric", metric="logger_type", value="legacy"}[5m]))
```

Then add a Grafana alert that fires whenever the recording rule is greater than
zero for two consecutive evaluations.

## Systemd timer alternative

```
# /etc/systemd/system/check-legacy-logger.service
[Unit]
Description=Sengoku legacy logger check

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 /opt/sengoku/scripts/check_legacy_logger_usage.py --minutes 10 --quiet

# /etc/systemd/system/check-legacy-logger.timer
[Unit]
Description=Run legacy logger check every 10 minutes

[Timer]
OnCalendar=*:0/10
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with:

```
sudo systemctl enable --now check-legacy-logger.timer
```

These examples ensure the metric is monitored continuously. Adjust paths,
intervals, and notification targets to suit your deployment.

For dashboard metrics based on the new `watchlist_*` events emitted by the ops
loop, use `scripts/metrics/watchlist_dashboard.py` to aggregate counts:

```
python3 scripts/metrics/watchlist_dashboard.py --log-dir /var/log/sengoku --files 3
```

Feed the plain-text output into a Prometheus textfile exporter or pass
`--as-json` for consumption by a log pipeline.
