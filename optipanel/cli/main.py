from __future__ import annotations

import argparse
import json
import logging
import os
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from optipanel.adapters.ibkr.iface import FeaturesProvider
from optipanel.alerts.engine import DEFAULT_THRESH, analyze_batch
from optipanel.engine.aggregate import build_symbol_snapshot
from optipanel.engine.scan import run_local_scan

_LOG_INITIALIZED = False


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


def alerts_cmd(symbols: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]
    return analyze_batch(snaps, DEFAULT_THRESH)


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
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    snaps = [build_symbol_snapshot(sym, feats) for sym, feats in symbols.items()]
    alerts = analyze_batch(snaps, DEFAULT_THRESH)
    print(json.dumps(alerts, indent=2, sort_keys=True))
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


def notify_cmd(symbols, iterations: int = 2):
    from optipanel.notify.engine import aggregate_alerts
    from optipanel.runtime.loop import run_once

    runs = [run_once(symbols) for _ in range(max(1, int(iterations)))]
    return aggregate_alerts(runs)


def notify_main(argv=None):
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="sengoku notify")
    ap.add_argument("--symbols-json", required=True)
    ap.add_argument("--iterations", type=int, default=2)
    args = ap.parse_args(argv)
    symbols = json.loads(args.symbols_json)
    out = notify_cmd(symbols, iterations=int(args.iterations))
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
