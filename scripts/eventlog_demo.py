#!/usr/bin/env python3
"""Demonstrate proper EventLogger usage with alerts."""

import json
import time
from pathlib import Path
from typing import Any

from optipanel.cli.main import build_symbol_snapshot, enrich_alerts_with_supply_sustain
from optipanel.ops.eventlog import EventLogger
from optipanel.runtime.loop import run_once


def log_alerts_with_context(alerts: list[dict[str, Any]], session_id: str) -> Path:
    """Log alerts with proper context and error handling.

    Args:
        alerts: List of alert dictionaries
        session_id: Unique identifier for this session

    Returns:
        Path to the log file written
    """
    logger = EventLogger()

    # Track the path for the first write
    log_path = None

    for alert in alerts:
        # Ensure alert is a dict
        if not isinstance(alert, dict):
            alert = {"raw": str(alert)}

        # Add session context
        enriched = {"session_id": session_id, "alert_seq": alerts.index(alert), **alert}

        # Remove None values to keep logs clean
        enriched = {k: v for k, v in enriched.items() if v is not None}

        # Emit the alert event
        path = logger.emit("alert", enriched)

        if log_path is None:
            log_path = path

    return log_path


def log_recon_decision(symbol: str, features: dict[str, Any], decision: str) -> None:
    """Log a recon decision with full context."""
    logger = EventLogger()

    # Build snapshot for enrichment
    snapshot = build_symbol_snapshot(symbol, features)

    # Extract key metrics
    readiness = snapshot.get("readiness", {})
    sustainment = snapshot.get("sustainment", {})

    logger.emit(
        "recon_decision",
        {
            "symbol": symbol,
            "decision": decision,
            "attack_ready": readiness.get("attack", 0),
            "defense_ready": readiness.get("defense", 0),
            "sustainability": sustainment.get("sustainability", 0),
            "fakeout_risk": sustainment.get("fakeout_risk", 0),
            "price": features.get("last", 0),
            "rvol": features.get("rvol", 0),
            "rs_strength": features.get("rs_strength", 0),
        },
    )


def demo_alert_logging():
    """Demonstrate alert logging with real market data."""

    # Session ID for correlation
    session_id = f"demo_{int(time.time())}"

    # Sample features for testing
    test_symbols = {
        "AAPL": {
            "last": 256.08,
            "dma20": 255.00,
            "support": 254.00,
            "resistance": 258.00,
            "rvol": 1.2,
            "rs_strength": 0.15,
            "vwap_diff": 0.008,
        },
        "MSFT": {
            "last": 514.45,
            "dma20": 512.00,
            "support": 510.00,
            "resistance": 516.00,
            "rvol": 1.1,
            "rs_strength": 0.10,
            "vwap_diff": 0.005,
        },
    }

    print(f"Starting alert logging demo (session: {session_id})")

    # Run the alert engine
    run_result = run_once(test_symbols)
    alerts = run_result.get("alerts", [])

    # Enrich alerts with supply and sustainment data
    base_snaps = [build_symbol_snapshot(sym, feats) for sym, feats in test_symbols.items()]
    enriched_alerts = enrich_alerts_with_supply_sustain(
        base_snaps,
        alerts,
        include_supply=True,
        include_sustain=True,
        include_readiness=True,
    )

    # Log all alerts
    if enriched_alerts:
        log_path = log_alerts_with_context(enriched_alerts, session_id)
        print(f"Logged {len(enriched_alerts)} alerts to: {log_path}")

        # Show what was logged
        print("\nLogged events:")
        with open(log_path) as f:
            for line in f:
                if session_id in line:
                    event = json.loads(line)
                    print(
                        f"  [{event['kind']}] {event.get('symbol', 'N/A')}: "
                        f"Attack={event.get('attack_ready', 'N/A')}%, "
                        f"Defense={event.get('defense_ready', 'N/A')}%"
                    )
    else:
        print("No alerts generated")

    # Log some recon decisions
    for symbol, features in test_symbols.items():
        decision = "BUY" if features["rs_strength"] > 0.12 else "HOLD"
        log_recon_decision(symbol, features, decision)
        print(f"Logged recon decision for {symbol}: {decision}")

    print(f"\nAll events logged to: {EventLogger()._root}")


def show_log_stats():
    """Display statistics about logged events."""
    logger = EventLogger()
    log_dir = logger._root

    print(f"\nEvent Log Statistics (from {log_dir}):")

    # Find all event files
    event_files = list(log_dir.glob("events-*.jsonl"))

    if not event_files:
        print("No event files found")
        return

    for file in sorted(event_files):
        event_counts = {}
        with open(file) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    kind = event.get("kind", "unknown")
                    event_counts[kind] = event_counts.get(kind, 0) + 1
                except json.JSONDecodeError:
                    pass

        print(f"\n  {file.name}:")
        for kind, count in sorted(event_counts.items()):
            print(f"    {kind}: {count} events")


if __name__ == "__main__":
    # Run the demo
    demo_alert_logging()

    # Show statistics
    show_log_stats()
