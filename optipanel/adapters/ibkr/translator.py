from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

try:
    from optipanel.indicators.intra import assemble_features_from_bars
except ImportError:  # pragma: no cover - defensive fallback
    logging.critical("Failed to import assemble_features_from_bars. Indicator calculation unavailable.")

    def assemble_features_from_bars(*args, **kwargs):  # type: ignore[return-type]
        return {}


logger = logging.getLogger(__name__)


def _extract_bars(data: Any) -> list[dict[str, Any]] | None:
    """Extract a list of OHLCV bar dicts from mixed fetcher payloads."""
    if isinstance(data, dict):
        bars = data.get("bars") or data.get("data") or data.get("ohlcv")
        if isinstance(bars, list):
            return bars
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            return data
    return None


def translate_bars_to_features(
    raw_data: dict[str, Any],
    benchmark_symbol: str | None = None,
    window: int = 20,
) -> dict[str, dict[str, Decimal]]:
    """
    Convert raw OHLCV bars into feature bundles using the intra-day indicators.
    """
    out: dict[str, dict[str, Decimal]] = {}

    if not raw_data or not isinstance(raw_data, dict):
        return out

    benchmark_bars = None
    if benchmark_symbol and benchmark_symbol in raw_data:
        benchmark_data = raw_data.get(benchmark_symbol)
        benchmark_bars = _extract_bars(benchmark_data)
        if not benchmark_bars:
            logger.warning(
                "Benchmark symbol %s found, but bar data is missing or invalid. RS inactive.",
                benchmark_symbol,
            )

    for sym, data in raw_data.items():
        if sym == benchmark_symbol:
            continue

        symbol_bars = _extract_bars(data)
        if not symbol_bars:
            logger.debug("Skipping feature calculation for %s due to missing or invalid bar data.", sym)
            out[sym] = {}
            continue

        try:
            features = assemble_features_from_bars(symbol_bars, benchmark_bars=benchmark_bars, window=window)
            out[sym] = features
        except Exception as exc:  # pragma: no cover - guardrails for live translators
            logger.error("Error calculating features for %s: %s", sym, exc, exc_info=True)
            out[sym] = {}

    return out


def translate_snapshots(raw: dict[str, Any], **kwargs: Any) -> dict[str, dict[str, Any]]:
    """
    Legacy pass-through for pre-computed feature snapshots.
    """
    if kwargs.get("benchmark_symbol"):
        logger.warning("LEGACY translate_snapshots called with benchmark_symbol; RS/VWAP remain unchanged.")

    out: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return out

    for sym, snap in raw.items():
        if isinstance(snap, dict):
            out[sym] = snap
        else:
            out[sym] = {}
    return out


def tws_translator(
    raw: dict[str, Any],
    benchmark_symbol: str | None = None,
    **kwargs: Any,
) -> dict[str, dict[str, Decimal]]:
    """
    Primary entry point for the TwsFeaturesProvider translator.
    """
    window = int(kwargs.get("window", 20))
    return translate_bars_to_features(raw, benchmark_symbol=benchmark_symbol, window=window)
