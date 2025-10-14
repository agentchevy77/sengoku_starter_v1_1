# Systemd Timer for Legacy Logger Monitoring

These unit files provide a ready-to-use systemd timer for running
`scripts/check_legacy_logger_usage.py` on production hosts.

## Installation

```
sudo cp check-legacy-logger.service /etc/systemd/system/
sudo cp check-legacy-logger.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now check-legacy-logger.timer
```

The timer executes the monitoring script every 10 minutes and raises a
non-zero exit status if any `logger_type="legacy"` metric is detected. Hook the
unit into your alerting system (journal scraping, systemd-notify, etc.) to
page the on-call team when it fails.

Adjust `ExecStart` paths as needed for your deployment layout.
