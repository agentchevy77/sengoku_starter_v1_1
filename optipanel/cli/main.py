from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from optipanel.acceptance.engine import detect_breakout_acceptance
from optipanel.adapters.ibkr.iface import FeaturesProvider
from optipanel.alerts.engine import DEFAULT_THRESH, analyze_batch_with_supply
from optipanel.chips.daily import compute_microchips_daily
from optipanel.chips.h60 import compute_microchips_h60
from optipanel.chips.m15 import compute_microchips_m15
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.engine.scan import run_local_scan
from optipanel.monitoring import evaluate_pacing_alerts, load_thresholds_from_env
from optipanel.recon.enrich import (
    build_recon_entry,
    enrich_alerts_with_gate,
    enrich_alerts_with_supply_sustain,
)
from optipanel.recon.readiness import readiness_from_front_sustain
from optipanel.setups.engine import compute_setups

_LOG_INITIALIZED = False

_MICRO_SPECS = (
    ("M15", "15m", compute_microchips_m15),
    ("H1", "60m", compute_microchips_h60),
    ("D1", "1d", compute_microchips_daily),
)

_PROB_KEYS = (
    ("breakout_up_prob", "brkU"),
    ("breakdown_down_prob", "brkD"),
    ("bounce_up_prob", "bUp"),
    ("rejection_down_prob", "rejD"),
    ("trend_long_prob", "trL"),
    ("trend_short_prob", "trS"),
)

_SUPPLY_ORDER = (
    "breakout_up",
    "trend_long",
    "breakdown_down",
    "trend_short",
    "bounce_up",
    "rejection_down",
    "exhaustion",
)


def _select_bundle(features: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    bundles = features.get("bundles") if isinstance(features, Mapping) else None
    if isinstance(bundles, Mapping):
        cand = bundles.get(key)
        if isinstance(cand, Mapping):
            return cand
    return features


def _format_prob_line(tf: str, block: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, label in _PROB_KEYS:
        if key in block:
            parts.append(f"{label}:{int(block[key]):02d}")
    return f"PROB     {tf:<3} " + " ".join(parts)


def _format_micro_line(tf: str, block: Mapping[str, Any]) -> str:
    keys = ("donchian", "trend_dma", "support_def", "res_clear", "rvol", "rs", "vwap")
    parts = [f"{k}:{int(block.get(k, 0)):02d}" for k in keys]
    return f"SCOUT    {tf:<3} " + " ".join(parts)


def _compute_micro_blocks(features: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    if not isinstance(features, Mapping):
        return rows
    for label, bundle_key, func in _MICRO_SPECS:
        source = _select_bundle(features, bundle_key)
        try:
            micro = func(dict(source))
        except Exception:
            micro = {}
        rows.append(_format_micro_line(label, micro))
    return rows


def _extract_bars(features: Mapping[str, Any] | None) -> list[Mapping[str, Any]] | None:
    if not isinstance(features, Mapping):
        return None
    for key in ("bars", "recent_bars", "ohlc"):
        candidate = features.get(key)
        if isinstance(candidate, list):
            return candidate
    return None


def _format_accept_line(features: Mapping[str, Any] | None) -> str | None:
    bars = _extract_bars(features)
    if not bars:
        return None
    resistance = features.get("resistance") if isinstance(features, Mapping) else None
    support = features.get("support") if isinstance(features, Mapping) else None

    def to_flag(value: bool) -> str:
        return "Y" if value else "N"

    candidate = None
    direction = None
    if resistance is not None:
        result = detect_breakout_acceptance(bars, resistance)
        if result["armed"] and result["debug"].get("direction") == "up":
            candidate = result
            direction = "UP"
    if candidate is None and support is not None:
        result = detect_breakout_acceptance(bars, support)
        if result["armed"] and result["debug"].get("direction") == "down":
            candidate = result
            direction = "DOWN"

    if candidate is None:
        return None

    line = f"ACCEPT   armed={to_flag(candidate['armed'])} accepted={to_flag(candidate['accepted'])}"
    if direction:
        line += f" dir={direction}"
    return line


def _render_recon_human(symbol: str, features: Mapping[str, Any], entry: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"=== RECON {symbol} ===")
    lines.append(f"SCOUT     recon [{int(entry.get('recon', 0)):3d}]")

    sustain = entry.get("sustainment", {})
    if isinstance(sustain, Mapping):
        sustain_val = int(sustain.get("sustainability", 50))
        fakeout_val = int(sustain.get("fakeout_risk", 50))
        lines.append(f"SUSTAIN   sustain={sustain_val:3d} fakeout={fakeout_val:3d}")

    readiness = entry.get("readiness") if isinstance(entry, Mapping) else None
    if isinstance(readiness, Mapping):
        attack = readiness.get("attack")
        defense = readiness.get("defense")
        if attack is not None and defense is not None:
            lines.append(f"READY     🗡{int(attack):3d}  🛡{int(defense):3d}")

    tf_map = entry.get("tf") or entry.get("timeframes") or {}
    for label in ("D", "H1", "M15"):
        block = tf_map.get(label)
        if isinstance(block, Mapping):
            lines.append(_format_prob_line(label, block))

    micro_rows = _compute_micro_blocks(features)
    lines.extend(micro_rows)

    accept_line = _format_accept_line(features)
    if accept_line:
        lines.append(accept_line)

    supply = entry.get("supply") if isinstance(entry, Mapping) else None
    if isinstance(supply, Mapping):
        for key in _SUPPLY_ORDER:
            factors = supply.get(key)
            if factors:
                lines.append(f"SUPPLY   {key:<13s} ⇐ {', '.join(factors)}")

    return "\n".join(lines)


def setup_logging() -> None:
    """Configure root logging with a per-session file handler."""

    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return

    level_name = os.environ.get("SENGOKU_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if os.environ.get("SENGOKU_DISABLE_FILE_LOGS"):
        logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")
        _LOG_INITIALIZED = True
        return

    root = Path(__file__).resolve().parents[2]
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"sengoku_{timestamp}.log"

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s", handlers=handlers)

    max_logs = int(os.environ.get("SENGOKU_MAX_LOG_FILES", "0"))
    if max_logs > 0:
        existing = sorted(log_dir.glob("sengoku_*.log"))
        excess = len(existing) - max_logs
        for stale in existing[:excess]:
            with suppress(Exception):
                stale.unlink()

    logging.info("Logging configured for session: %s", log_file)
    _LOG_INITIALIZED = True


# Programmatic helpers (pure)
def snapshot_cmd(symbol: str, features: dict[str, Any]) -> dict[str, Any]:
    return build_symbol_snapshot(symbol, features)


def scan_cmd(symbols: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return run_local_scan(symbols)


def alerts_cmd(
    symbols: dict[str, dict[str, Any]],
    *,
    include_supply: bool = False,
) -> list[dict[str, Any]]:
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]
    return analyze_batch_with_supply(
        snaps,
        DEFAULT_THRESH,
        include_supply=include_supply,
    )


def loop_cmd(symbols, iterations: int = 2) -> list[dict]:
    from optipanel.runtime.loop import run_once

    out = []
    for _ in range(max(1, int(iterations))):
        out.append(run_once(symbols))
    return out


def driver_cmd(symbols, profile, ticks: int = 5):
    from optipanel.runtime.driver import run_driver

    return run_driver(symbols, profile, ticks=int(ticks))


def command_room_cmd(symbols, width: int = 24, top_n: int = 1, iterations: int = 1):
    from optipanel.runtime.loop import run_once
    from optipanel.ui.command_room import render_command_room

    outs = []
    for _ in range(max(1, int(iterations))):
        outs.append(render_command_room(run_once(symbols), width=width, top_n=top_n))
    return "\n---\n".join(outs)


def profiles_cmd(profiles_yaml_text: str, features_yaml_text: str, ticks: int = 3) -> dict[str, Any]:
    from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
    from optipanel.runtime.profiles import run_profiles_offline

    prof = parse_profiles_yaml(profiles_yaml_text)
    feats = parse_features_yaml(features_yaml_text)
    return run_profiles_offline(prof, feats, ticks=int(ticks))


# CLI entry points (print JSON / ASCII; return exit codes)
def snapshot_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku snapshot")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--features-json", required=True)
    args = ap.parse_args(argv)
    features = json.loads(args.features_json)
    snap = build_symbol_snapshot(args.symbol, features)
    print(json.dumps(snap, indent=2, sort_keys=True))
    return 0


def scan_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku scan")
    ap.add_argument("--symbols-json", required=True)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    out = run_local_scan(symbols)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def alerts_main(argv=None):
    ap = argparse.ArgumentParser(prog="sengoku alerts")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument(
        "--include-supply",
        action="store_true",
        help="Include supply lines in alert payloads",
    )
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    include_supply = args.include_supply or os.getenv("SENGOKU_ALERTS_INCLUDE_SUPPLY", "") == "1"
    alerts = alerts_cmd(symbols, include_supply=include_supply)
    print(json.dumps(alerts, indent=2, sort_keys=True))
    return 0


def health_main(*, ping: bool = False) -> int:
    from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
    from optipanel.runtime.health import get_ibkr_health, get_runtime_health

    fetcher = RealTwsFetcher(cfg_from_env())
    if ping:
        from contextlib import suppress

        with suppress(Exception):
            fetcher.handshake_test()

    ibkr_info = get_ibkr_health(fetcher)
    pacing_metrics = fetcher.pacing_metrics()
    ibkr_info["pacing"] = pacing_metrics
    pacing_overrides = load_thresholds_from_env()
    pacing_alerts = evaluate_pacing_alerts(
        pacing_metrics,
        thresholds=pacing_overrides if pacing_overrides else None,
    )
    if pacing_alerts:
        ibkr_info["pacing_alerts"] = [asdict(a) for a in pacing_alerts]
    if pacing_overrides:
        ibkr_info["pacing_thresholds"] = pacing_overrides

    payload = get_runtime_health(extra={"ibkr": ibkr_info})
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def loop_main(argv=None):
    import time

    from optipanel.runtime.loop import run_once

    ap = argparse.ArgumentParser(prog="sengoku loop")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between iterations (0 for none)")
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    runs = []
    for _ in range(max(1, int(args.iterations))):
        runs.append(run_once(symbols))
        if args.sleep > 0:
            time.sleep(args.sleep)
    print(json.dumps({"iterations": int(args.iterations), "runs": runs}, indent=2, sort_keys=True))
    return 0


def _render_command_room_panel(mode: str, text: str) -> str:
    return text.replace("COMMAND ROOM (", f"COMMAND ROOM ({mode}")


def command_room_main(argv=None):
    import time

    from optipanel.runtime.loop import run_once
    from optipanel.ui.command_room import render_command_room

    ap = argparse.ArgumentParser(prog="sengoku command-room")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--width", type=int, default=24)
    ap.add_argument("--top-n", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=0.0)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    chunks = []
    for i in range(max(1, int(args.iterations))):
        chunks.append(render_command_room(run_once(symbols), width=int(args.width), top_n=int(args.top_n)))
        if args.sleep > 0 and i + 1 < int(args.iterations):
            time.sleep(args.sleep)
    print("\n---\n".join(chunks))
    return 0


def driver_main(argv=None):
    import time

    from optipanel.runtime.driver import run_driver

    ap = argparse.ArgumentParser(prog="sengoku driver")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument(
        "--profile-json",
        required=True,
        help='JSON: {"soft_cap":int,"cooldown":int,"used_lines":int|[...],"scan_stride_backoff":int}',
    )
    ap.add_argument("--ticks", type=int, default=5)
    ap.add_argument("--sleep", type=float, default=0.0)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    profile = json.loads(args.profile_json)
    out = run_driver(symbols, profile, ticks=int(args.ticks))
    if args.sleep > 0:
        time.sleep(args.sleep)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def profiles_main(argv=None):
    import pathlib

    from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
    from optipanel.runtime.profiles import run_profiles_offline

    ap = argparse.ArgumentParser(prog="sengoku profiles")
    ap.add_argument("--profiles-yaml", required=True)
    ap.add_argument("--features-yaml", required=True)
    ap.add_argument("--ticks", type=int, default=3)
    ap.add_argument("--tws-host", default="127.0.0.1")
    ap.add_argument("--tws-port", type=int, default=7497)
    ap.add_argument("--client-id", type=int, default=107)
    ap.add_argument("--ref-symbol", default="SPY")
    args = ap.parse_args(argv)
    prof_txt = pathlib.Path(args.profiles_yaml).read_text()
    feat_txt = pathlib.Path(args.features_yaml).read_text()
    prof = parse_profiles_yaml(prof_txt)
    feats = parse_features_yaml(feat_txt)
    out = run_profiles_offline(prof, feats, ticks=int(args.ticks))
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def snapshot_cmd_alias(argv=None):  # legacy alias kept for completeness
    return snapshot_main(argv)


def main(argv=None):
    setup_logging()
    p = argparse.ArgumentParser(prog="sengoku")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="Print a single symbol snapshot")
    s.add_argument("--symbol", required=True)
    s.add_argument("--features-json", required=True)

    sc = sub.add_parser("scan", help="Rank multiple symbols")
    sc.add_argument("--symbols-json", required=True)

    a = sub.add_parser("alerts", help="Generate alerts for multiple symbols")
    a.add_argument("--symbols-json", required=True)

    lp = sub.add_parser("loop", help="Run repeated scans (pure, offline)")
    lp.add_argument("--symbols-json", required=True)
    lp.add_argument("--iterations", type=int, default=2)
    lp.add_argument("--sleep", type=float, default=0.0)

    op = sub.add_parser("ops", help="Run Prime/Secondary scheduling loop")
    op.add_argument("--profiles-yaml", required=True)
    op.add_argument("--provider", choices=["tws-live", "mock"], default="tws-live")
    op.add_argument("--ticks", type=int, default=10)
    op.add_argument("--sleep", type=float, default=0)
    op.add_argument("--width", type=int, default=24)
    op.add_argument("--top-n", type=int, default=2)

    hp = sub.add_parser("health", help="Diagnose IBKR connectivity and cache state")
    hp.add_argument("--ping", action="store_true", help="Attempt handshake() to refresh IBKR status")

    cr = sub.add_parser("command-room", help="ASCII dashboard panel")
    cr.add_argument("--symbols-json", required=True)
    cr.add_argument("--width", type=int, default=24)
    cr.add_argument("--top-n", type=int, default=1)
    cr.add_argument("--iterations", type=int, default=1)
    cr.add_argument("--sleep", type=float, default=0.0)

    d = sub.add_parser("driver", help="Budget-aware tick driver (offline)")
    d.add_argument("--symbols-json", required=True)
    d.add_argument("--profile-json", required=True)
    d.add_argument("--ticks", type=int, default=5)
    d.add_argument("--sleep", type=float, default=0.0)

    pr = sub.add_parser("profiles", help="Run Prime/Secondary profiles (offline)")
    nt = sub.add_parser("notify", help="Aggregate alerts into a deduped event list")
    nt.add_argument("--symbols-json", required=True)
    nt.add_argument("--iterations", type=int, default=2)
    rc = sub.add_parser("recon", help="Compute recon chips composite")
    rc.add_argument("--symbols", required=True)
    rc.add_argument("--provider", choices=["tws-live", "mock"], default="tws-live")
    rc.add_argument("--features-yaml")
    rc.add_argument(
        "--mode",
        choices=["prob", "micro"],
        default="prob",
        help="Recon lens for chips-by-timeframe",
    )
    rc.add_argument("--include-supply", action="store_true")
    rc.add_argument("--json-include", default="")
    rc.add_argument("--pretty", action="store_true")
    prl = sub.add_parser("profiles-live", help="Run profiles with a provider (mock for now)")
    prl.add_argument("--profiles-yaml", required=True)
    prl.add_argument("--provider", default="mock", choices=["mock", "tws-mock", "tws-live"])
    prl.add_argument("--features-yaml")
    prl.add_argument("--ticks", type=int, default=3)
    prl.add_argument("--tws-host", default="127.0.0.1")
    prl.add_argument("--tws-port", type=int, default=7497)
    prl.add_argument("--client-id", type=int, default=107)
    prl.add_argument("--ref-symbol", default="SPY")
    pr.add_argument("--profiles-yaml", required=True)
    pr.add_argument("--features-yaml", required=True)
    pr.add_argument("--ticks", type=int, default=3)

    args = p.parse_args(argv)
    if args.cmd == "snapshot":
        return snapshot_main(["--symbol", args.symbol, "--features-json", args.features_json])
    if args.cmd == "scan":
        return scan_main(["--symbols-json", args.symbols_json])
    if args.cmd == "alerts":
        return alerts_main(["--symbols-json", args.symbols_json])
    if args.cmd == "health":
        return health_main(ping=getattr(args, "ping", False))
    if args.cmd == "loop":
        return loop_main(
            [
                "--symbols-json",
                args.symbols_json,
                "--iterations",
                str(args.iterations),
                "--sleep",
                str(args.sleep),
            ]
        )
    if args.cmd == "ops":
        from optipanel.adapters.ibkr import MockFeaturesProvider, RealTwsFetcher, cfg_from_env
        from optipanel.config.loader import parse_profiles_yaml
        from optipanel.ops.ops_loop import ops_loop

        profiles_text = Path(args.profiles_yaml).read_text(encoding="utf-8")
        profile = parse_profiles_yaml(profiles_text)

        provider = RealTwsFetcher(cfg_from_env()) if args.provider == "tws-live" else MockFeaturesProvider({})

        ops_loop(
            provider,
            profile,
            ticks=int(args.ticks),
            sleep=float(args.sleep),
            width=int(args.width),
            top_n=int(args.top_n),
        )
        print()
        return 0
    if args.cmd == "command-room":
        return command_room_main(
            [
                "--symbols-json",
                args.symbols_json,
                "--width",
                str(getattr(args, "width", 24)),
                "--top-n",
                str(getattr(args, "top_n", 1)),
                "--iterations",
                str(getattr(args, "iterations", 1)),
                "--sleep",
                str(getattr(args, "sleep", 0.0)),
            ]
        )
    if args.cmd == "driver":
        return driver_main(
            [
                "--symbols-json",
                args.symbols_json,
                "--profile-json",
                args.profile_json,
                "--ticks",
                str(getattr(args, "ticks", 5)),
                "--sleep",
                str(getattr(args, "sleep", 0.0)),
            ]
        )
    if args.cmd == "profiles":
        return profiles_main(
            [
                "--profiles-yaml",
                args.profiles_yaml,
                "--features-yaml",
                args.features_yaml,
                "--ticks",
                str(getattr(args, "ticks", 3)),
            ]
        )
    if args.cmd == "notify":
        return notify_main(
            [
                "--symbols-json",
                args.symbols_json,
                "--iterations",
                str(getattr(args, "iterations", 2)),
            ]
        )
    if args.cmd == "recon":
        inner_argv = ["--symbols", args.symbols, "--provider", args.provider]
        if getattr(args, "features_yaml", None):
            inner_argv += ["--features-yaml", args.features_yaml]
        inner_argv += ["--mode", args.mode]
        if getattr(args, "include_supply", False):
            inner_argv.append("--include-supply")
        if getattr(args, "json_include", ""):
            inner_argv += ["--json-include", args.json_include]
        if getattr(args, "pretty", False):
            inner_argv.append("--pretty")
        return recon_main(inner_argv)
    if args.cmd == "profiles-live":
        return profiles_live_main(
            [
                "--profiles-yaml",
                args.profiles_yaml,
                "--provider",
                args.provider,
                "--features-yaml",
                getattr(args, "features_yaml", None) or "",
                "--ticks",
                str(getattr(args, "ticks", 3)),
                "--tws-host",
                getattr(args, "tws_host", "127.0.0.1"),
                "--tws-port",
                str(getattr(args, "tws_port", 7497)),
                "--client-id",
                str(getattr(args, "client_id", 107)),
                "--ref-symbol",
                getattr(args, "ref_symbol", "SPY"),
            ]
        )
    p.error("unknown command")


def profiles_live_cmd(
    profiles_yaml_text: str,
    provider: str,
    features_yaml_text: str | None,
    ticks: int = 3,
    *,
    tws_host: str | None = None,
    tws_port: int | None = None,
    tws_client_id: int | None = None,
    tws_ref_symbol: str | None = None,
):
    """
    Live profiles runner with three providers:
      - mock:      features_yaml -> MockFeaturesProvider
      - tws-mock:  TWS-shaped mock fetcher -> translator
      - tws-live:  Real IBKR TWS via ibapi (env-configured) -> translator
    """
    from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
    from optipanel.runtime.profiles_live import run_profiles_with_provider

    prov: FeaturesProvider

    def _require_features(text: str | None, provider_name: str) -> str:
        if text is None:
            raise ValueError(f"features-yaml is required for provider={provider_name}")
        return text

    if provider == "mock":
        # simple dict-based features provider
        feats_txt = _require_features(features_yaml_text, "mock")
        feats = parse_features_yaml(feats_txt)
        from optipanel.adapters.ibkr import MockFeaturesProvider

        prov = MockFeaturesProvider(feats)

    elif provider == "tws-mock":
        # TWS-shaped mock fetch -> translator -> features
        feats_txt = _require_features(features_yaml_text, "tws-mock")
        feats = parse_features_yaml(feats_txt)
        from optipanel.adapters.ibkr import TwsFeaturesProvider
        from optipanel.adapters.ibkr.fetchers_mock import MockTwsFetcher
        from optipanel.adapters.ibkr.translator import translate_snapshots

        prov = TwsFeaturesProvider(fetcher=MockTwsFetcher(feats), translator=translate_snapshots)

    elif provider == "tws-live":
        # Real TWS fetch via ibapi; read connection from environment or globals
        import os

        from optipanel.adapters.ibkr import RealTwsFetcher, RealTwsFetcherConfig
        from optipanel.adapters.ibkr.translator import translate_snapshots

        host = tws_host or os.environ.get("SENGOKU_TWS_HOST") or "127.0.0.1"
        port_env = os.environ.get("SENGOKU_TWS_PORT") if tws_port is None else tws_port
        client_env = os.environ.get("SENGOKU_TWS_CLIENT_ID") if tws_client_id is None else tws_client_id
        ref_symbol_env = os.environ.get("SENGOKU_TWS_REF") if tws_ref_symbol is None else tws_ref_symbol

        port = int(port_env) if port_env is not None else 7497
        client_id = int(client_env) if client_env is not None else 107
        ref_symbol = str(ref_symbol_env) if ref_symbol_env is not None else "SPY"

        cfg = RealTwsFetcherConfig(host=host, port=port, client_id=client_id, ref_symbol=ref_symbol)
        fetcher = RealTwsFetcher(cfg)
        # minimal provider wrapper to fit the existing runtime
        prov = cast(
            FeaturesProvider,
            type(
                "Proxy",
                (),
                {
                    "features_for_symbols": lambda self, syms: (
                        fetcher.features_for_symbols(list(syms))
                        if hasattr(fetcher, "features_for_symbols")
                        else translate_snapshots(fetcher(list(syms)))
                    )
                },
            )(),
        )

    else:
        raise ValueError("Unsupported provider (use 'mock', 'tws-mock' or 'tws-live')")

    prof = parse_profiles_yaml(profiles_yaml_text)
    return run_profiles_with_provider(prof, prov, ticks=int(ticks))


def profiles_live_main(argv=None):
    import argparse
    import json
    import pathlib

    ap = argparse.ArgumentParser(prog="sengoku profiles-live")
    ap.add_argument("--profiles-yaml", required=True)
    ap.add_argument("--provider", default="mock", choices=["mock", "tws-mock", "tws-live"])  # 'tws' soon
    ap.add_argument("--features-yaml")  # required for mock
    ap.add_argument("--ticks", type=int, default=3)
    ap.add_argument("--tws-host", default="127.0.0.1")
    ap.add_argument("--tws-port", type=int, default=7497)
    ap.add_argument("--client-id", type=int, default=107)
    ap.add_argument("--ref-symbol", default="SPY")
    args = ap.parse_args(argv)
    prof_txt = pathlib.Path(args.profiles_yaml).read_text()
    feats_txt = pathlib.Path(args.features_yaml).read_text() if args.features_yaml else None
    out = profiles_live_cmd(
        prof_txt,
        args.provider,
        feats_txt,
        ticks=int(args.ticks),
        tws_host=args.tws_host,
        tws_port=args.tws_port,
        tws_client_id=args.client_id,
        tws_ref_symbol=args.ref_symbol,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def notify_cmd(
    symbols,
    iterations: int = 2,
    *,
    include_supply: bool = False,
    require_acceptance: bool = False,
    ready_min: int = 65,
    armed_floor: int = 50,
):
    from optipanel.notify.engine import aggregate_alerts
    from optipanel.runtime.loop import run_once

    iterations = max(1, int(iterations))
    base_snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]

    runs = []
    for _ in range(iterations):
        run = run_once(symbols)
        alerts = run.get("alerts") if isinstance(run, dict) else None
        alerts = enrich_alerts_with_supply_sustain(
            base_snaps,
            alerts,
            include_supply=include_supply,
            include_sustain=True,
        )
        alerts = enrich_alerts_with_gate(
            base_snaps,
            alerts,
            require_acceptance=require_acceptance,
            ready_min=ready_min,
            armed_floor=armed_floor,
        )
        run["alerts"] = alerts
        runs.append(run)
    return aggregate_alerts(runs)


def notify_main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="sengoku notify")
    ap.add_argument("--require-acceptance", action="store_true", help="drop alerts unless gate=go")
    ap.add_argument("--ready-min", type=int, default=None, help="readiness threshold for gate=go (default 65)")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument(
        "--include-supply",
        action="store_true",
        help="Include SUPPLY lines in alert payloads",
    )
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    include_supply = args.include_supply or os.getenv("SENGOKU_NOTIFY_INCLUDE_SUPPLY", "") == "1"

    def _env_truth(value: str | None) -> bool:
        if not value:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    env_accept = os.getenv("SENGOKU_NOTIFY_REQUIRE_ACCEPT")
    require_acceptance = args.require_acceptance or _env_truth(env_accept)
    env_ready = os.getenv("SENGOKU_NOTIFY_READY_MIN")
    ready_min = args.ready_min if args.ready_min is not None else int(env_ready) if env_ready else 65
    out = notify_cmd(
        symbols,
        iterations=int(args.iterations),
        include_supply=include_supply,
        require_acceptance=require_acceptance,
        ready_min=int(ready_min),
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def recon_main(argv=None):
    import argparse
    import json
    from pathlib import Path

    from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
    from optipanel.config.loader import parse_features_yaml

    ap = argparse.ArgumentParser(prog="sengoku recon")
    ap.add_argument("--symbols", required=True, help="Comma-separated symbol list")
    ap.add_argument("--provider", choices=["tws-live", "mock"], default="tws-live")
    ap.add_argument("--features-yaml", help="Required when provider=mock")
    ap.add_argument(
        "--mode",
        choices=["prob", "micro"],
        default="prob",
        help="Recon lens for chips-by-timeframe (prob canonical, micro for scout)",
    )
    ap.add_argument("--pretty", action="store_true", help="Pretty-print recon view instead of JSON")
    ap.add_argument("--include-supply", action="store_true", help="Include supply factors in JSON output")
    ap.add_argument("--json-include", default="", help="Comma list of extras (e.g. chips_summary)")
    args = ap.parse_args(argv)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        raise SystemExit("No symbols specified")

    include_flags = {flag.strip() for flag in (args.json_include or "").split(",") if flag.strip()}
    include_supply = args.include_supply or os.getenv("SENGOKU_RECON_SUPPLY_DEFAULT", "") == "1"
    include_summary = "chips_summary" in include_flags

    if args.provider == "mock":
        if not args.features_yaml:
            raise SystemExit("--features-yaml is required for provider=mock")
        feats_txt = Path(args.features_yaml).read_text()
        features = parse_features_yaml(feats_txt)
    else:
        fetcher = RealTwsFetcher(cfg_from_env())
        features = fetcher.features_for_symbols(symbols)

    output: dict[str, dict[str, object]] = {}
    pretty_chunks: list[str] = []
    for sym in symbols:
        feat = features.get(sym, {}) or {}
        if not isinstance(feat, dict):
            feat = dict(feat)
        entry = build_recon_entry(
            feat,
            mode=args.mode,
            include_supply=include_supply,
            include_summary=include_summary,
        )
        chips_by_tf = entry.get("tf", {})
        sustainment = entry.get("sustainment", {})
        front_units = compute_setups(dict(features))
        acceptance_score = None
        raw_accept = features.get("acceptance") if isinstance(features, Mapping) else None
        if isinstance(raw_accept, Mapping):
            summary = raw_accept.get("summary")
            if isinstance(summary, Mapping):
                acceptance_score = summary.get("score")
        readiness_data = readiness_from_front_sustain(front_units, sustainment, acceptance_score)
        shaped: dict[str, Any] = {
            "timeframes": chips_by_tf,
            "aggregate": entry.get("agg", {}),
            "recon": entry.get("recon", 0),
            "sustainment": sustainment,
            "mode": entry.get("mode", args.mode),
            "readiness": readiness_data,
        }
        if include_summary and entry.get("chips_summary"):
            shaped["chips_summary"] = entry["chips_summary"]
        if include_supply and entry.get("supply"):
            shaped["supply"] = entry["supply"]
        if entry.get("tf_scout"):
            shaped["tf_scout"] = entry["tf_scout"]
        output[sym] = shaped
        if args.pretty:
            pretty_chunks.append(_render_recon_human(sym, feat, shaped))

    if args.pretty:
        print("\n\n".join(pretty_chunks))
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
