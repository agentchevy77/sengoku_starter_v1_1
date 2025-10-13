"""Intraday indicator helpers and feature bundle assembly."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

# Import Decimal utilities established during stabilization phase
try:
    from optipanel.utils.decimal_types import (
        D_HALF,
        D_ONE,
        D_ZERO,
        safe_divide,
        to_decimal,
    )
except ImportError:  # pragma: no cover - exercised only when utils unavailable
    # Define minimal fallbacks if utils are missing (for robustness)
    logging.warning("Failed to import decimal_types utils. Using fallback definitions.")
    D_ZERO = Decimal("0.0")
    D_ONE = Decimal("1.0")
    D_HALF = Decimal("0.5")

    # Fallback definitions are simplified for emergency use
    def to_decimal(val: Any, default: Decimal | None = None) -> Decimal | None:
        try:
            return Decimal(str(val))
        except (InvalidOperation, TypeError, ValueError):
            return default

    def safe_divide(numerator: Decimal, denominator: Decimal, default: Decimal = D_ZERO) -> Decimal:
        if not denominator:
            return default
        try:
            return numerator / denominator
        except (InvalidOperation, ZeroDivisionError):
            return default


logger = logging.getLogger(__name__)

# Define type aliases for clarity
DecimalList = list[Decimal]


def _clip(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    """Clamp *value* into the inclusive range [lower, upper]."""
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _as_decimal_sequence(values: Iterable[Any], context: str) -> DecimalList:
    """Safely converts an iterable of various types to a list of finite Decimals."""
    result: DecimalList = []
    for idx, value in enumerate(values):
        # Use the standardized utility function for robust conversion
        dec_val = to_decimal(value, default=None)

        if dec_val is None or not dec_val.is_finite():
            # Log non-finite or invalid values and skip them.
            # Alignment must be handled by the caller.
            logger.warning(
                "indicators.intra: Skipping invalid or non-finite value at index %d for %s: %r",
                idx,
                context,
                value,
            )
            continue
        result.append(dec_val)
    return result


def donchian_pos(highs: DecimalList, lows: DecimalList, close: Decimal) -> Decimal:
    """Return position of *close* within the high/low channel as 0..1."""
    # Rely on inputs being valid lists from upstream processing, but handle empty lists.
    if not highs or not lows:
        return D_HALF

    hi = max(highs)
    lo = min(lows)
    span = hi - lo

    # Use safe_divide, defaulting to midpoint if span is zero (High == Low across the window).
    pos = safe_divide(close - lo, span, default=D_HALF)

    return _clip(pos, D_ZERO, D_ONE)


def clv(open_: Decimal, high: Decimal, low: Decimal, close: Decimal) -> Decimal:
    """Close Location Value scaled to [-1, 1]; graceful on degenerate bars."""
    span = high - low

    # Numerator: ((close - low) - (high - close)) simplifies to (2 * close - low - high)
    numerator = (Decimal("2") * close) - low - high

    # Use safe_divide, defaulting to 0.0 (midpoint) if span is zero (High == Low)
    value = safe_divide(numerator, span, default=D_ZERO)

    return _clip(value, Decimal("-1.0"), D_ONE)


def _normalized_slope(values: Sequence[Decimal]) -> Decimal:
    """Calculates the slope normalized to a [-1, 1] range."""
    if len(values) < 2:
        return D_ZERO

    start = values[0]
    end = values[-1]
    diff = end - start

    # Determine the scale factor for normalization
    try:
        max_val = abs(max(values))
        min_val = abs(min(values))
        # Scale by the largest magnitude observed, ensuring scale is at least 1.0
        scale = max(max_val, min_val, abs(diff), D_ONE)
    except (ValueError, InvalidOperation, TypeError):
        # Handle potential errors if values list contains invalid data despite upstream checks
        return D_ZERO

    # Use safe_divide (though scale >= 1.0)
    slope = safe_divide(diff, scale, default=D_ZERO)

    return _clip(slope, Decimal("-1.0"), D_ONE)


def obv_slope(closes: DecimalList, volumes: DecimalList, window: int = 20) -> Decimal:
    """On-Balance Volume slope normalised to [-1, 1]."""
    # Lists are assumed aligned and trimmed by assemble_features_from_bars
    n = len(closes)
    if n < 2:
        return D_ZERO

    obv: DecimalList = [D_ZERO]
    for idx in range(1, n):
        prev_close = closes[idx - 1]
        cur_close = closes[idx]
        delta = volumes[idx]

        if cur_close > prev_close:
            obv.append(obv[-1] + delta)
        elif cur_close < prev_close:
            obv.append(obv[-1] - delta)
        else:
            obv.append(obv[-1])

    span = min(window, len(obv) - 1)
    return _normalized_slope(obv[-(span + 1) :])


def chaikin_ad_slope(
    highs: DecimalList,
    lows: DecimalList,
    closes: DecimalList,
    volumes: DecimalList,
    window: int = 20,
) -> Decimal:
    """Chaikin Accumulation/Distribution slope normalised to [-1, 1]."""
    # Lists are assumed aligned and trimmed
    n = len(closes)
    if n < 1:
        return D_ZERO

    ad: DecimalList = [D_ZERO]
    for idx in range(n):
        high = highs[idx]
        low = lows[idx]
        close = closes[idx]
        volume = volumes[idx]

        # Calculate Money Flow Multiplier using CLV logic
        spread = high - low
        # Numerator: (2 * close - low - high)
        numerator = (Decimal("2") * close) - low - high
        money_flow = safe_divide(numerator, spread, default=D_ZERO)

        ad.append(ad[-1] + money_flow * volume)

    if len(ad) < 2:
        return D_ZERO

    span = min(window, len(ad) - 1)
    return _normalized_slope(ad[-(span + 1) :])


def rvol_ratio(volumes: DecimalList, recent: int = 20, baseline: int = 60) -> Decimal:
    """Return recent-average / baseline-average volume ratio."""
    n = len(volumes)
    if n < max(recent, baseline) or recent <= 0:
        return D_ONE

    recent = min(recent, n)
    baseline = min(baseline, n)

    # Ensure baseline window is longer than recent window
    if baseline <= recent:
        baseline = min(n, recent + max(1, recent // 2))

    recent_slice = volumes[-recent:]
    # Baseline slice excludes the recent slice
    baseline_slice = volumes[-baseline:-recent]

    if not baseline_slice:
        return D_ONE

    # Calculate averages
    recent_avg = sum(recent_slice) / len(recent_slice)
    baseline_avg = sum(baseline_slice) / len(baseline_slice)

    # Use safe_divide, defaulting to 1.0 if baseline is zero/negative
    ratio = safe_divide(recent_avg, baseline_avg, default=D_ONE)

    return max(D_ZERO, ratio)


def _safe_percentage_change(start_val: Decimal, end_val: Decimal) -> Decimal:
    """Calculate percentage change safely, handling zero start value."""
    # Using abs(start_val) in denominator is standard for robust percentage change.
    return safe_divide(end_val - start_val, abs(start_val), default=D_ZERO)


def _calculate_relative_strength(
    closes: Sequence[Decimal],
    benchmark_closes: Sequence[Decimal],
    window: int,
) -> Decimal:
    """Calculate the performance difference (Alpha) between a stock and a benchmark."""
    if not closes or not benchmark_closes or window <= 0:
        return D_ZERO

    # Ensure lookback is synchronized across both sequences
    lookback = min(window, len(closes), len(benchmark_closes))
    if lookback < 2:
        # Need at least two points to calculate change
        return D_ZERO

    # Determine the start and end points for the calculation window
    start_price = closes[-lookback]
    end_price = closes[-1]

    start_benchmark = benchmark_closes[-lookback]
    end_benchmark = benchmark_closes[-1]

    # Calculate performance using the safe helper
    stock_perf = _safe_percentage_change(start_price, end_price)
    bench_perf = _safe_percentage_change(start_benchmark, end_benchmark)

    return stock_perf - bench_perf


def _calculate_vwap(closes: DecimalList, volumes: DecimalList) -> Decimal:
    """Calculate the Volume-Weighted Average Price over the given data."""
    # Lists are assumed aligned and trimmed
    if not closes:
        return D_ZERO

    cumulative_volume = D_ZERO
    cumulative_pv = D_ZERO  # Price * Volume

    for price, volume in zip(closes, volumes, strict=False):
        # Basic sanity check for inputs (e.g., negative volume or non-positive price)
        # This is crucial as _as_decimal_sequence might skip entries but not guarantee positivity.
        if volume < D_ZERO or price <= D_ZERO:
            continue

        cumulative_volume += volume
        cumulative_pv += price * volume

    # Use safe_divide to handle cases where total volume might be zero
    return safe_divide(cumulative_pv, cumulative_volume, default=D_ZERO)


def assemble_features_from_bars(
    bars: Sequence[dict[str, Any]],
    benchmark_bars: Sequence[dict[str, Any]] | None = None,
    window: int = 20,
) -> dict[str, Decimal]:
    """Assemble a feature bundle from OHLCV bars using safe defaults and Decimal precision."""

    # Define default return structure
    defaults = {
        "last": D_ZERO,
        "dma20": D_ZERO,
        "support": D_ZERO,
        "resistance": D_ZERO,
        "rvol": D_ONE,
        "rs_strength": D_ZERO,
        "vwap_diff": D_ZERO,
        "donchian_pos": D_HALF,
        "avwap_diff": D_ZERO,  # Using AVWAP synonymously with session VWAP here
        "obv_slope": D_ZERO,
        "chaikin_ad": D_ZERO,
        "clv": D_ZERO,
        "vwap_confluence": D_ZERO,  # Remains stubbed pending multi-timeframe input
    }

    if not bars:
        return defaults

    # Extract data and convert to Decimal sequences safely.
    # Note: _as_decimal_sequence skips invalid entries.
    closes = _as_decimal_sequence([bar.get("c") for bar in bars], "closes")
    highs = _as_decimal_sequence([bar.get("h") for bar in bars], "highs")
    lows = _as_decimal_sequence([bar.get("l") for bar in bars], "lows")
    opens = _as_decimal_sequence([bar.get("o") for bar in bars], "opens")
    volumes = _as_decimal_sequence([bar.get("v") for bar in bars], "volumes")

    # Ensure all lists have the same length after filtering invalid entries (Crucial for alignment)
    min_len = min(len(closes), len(highs), len(lows), len(opens), len(volumes))
    if min_len == 0:
        return defaults

    # Trim lists to the minimum length to ensure synchronization for calculations
    closes = closes[-min_len:]
    highs = highs[-min_len:]
    lows = lows[-min_len:]
    opens = opens[-min_len:]
    volumes = volumes[-min_len:]

    # Process benchmark data if provided
    benchmark_closes: DecimalList = []
    if benchmark_bars:
        benchmark_closes = _as_decimal_sequence([bar.get("c") for bar in benchmark_bars], "benchmark_closes")

    # Define the lookback window for calculations
    lookback = min(window, min_len)
    closes_win = closes[-lookback:]
    highs_win = highs[-lookback:]
    lows_win = lows[-lookback:]

    # --- Calculations ---

    # 1. Basic Metrics
    last_price = closes[-1]
    dma = sum(closes_win) / len(closes_win)
    support = min(lows_win)
    resistance = max(highs_win)

    # 2. Volume Metrics
    recent_vol_window = min(20, min_len)
    baseline_window = min(60, min_len)
    rvol = rvol_ratio(volumes, recent=recent_vol_window, baseline=baseline_window)

    # 3. Relative Strength (Task 1.1)
    rs_strength = _calculate_relative_strength(closes, benchmark_closes, lookback)

    # 4. VWAP Family (Task 1.2)
    # We calculate VWAP over the entire provided sequence (assuming it represents the session)
    # This serves as both the standard VWAP and the AVWAP anchored to the session open.
    session_vwap = _calculate_vwap(closes, volumes)

    # Calculate the percentage difference between the last price and the session VWAP
    vwap_diff = _safe_percentage_change(session_vwap, last_price)
    # In this context, avwap_diff is the same as vwap_diff
    avwap_diff = vwap_diff

    # 5. Other Indicators
    donchian = donchian_pos(highs_win, lows_win, last_price)
    obv = obv_slope(closes, volumes, window=min(20, min_len))
    chaikin_ad = chaikin_ad_slope(highs, lows, closes, volumes, window=min(20, min_len))

    # Use the last complete bar for CLV calculation
    last_clv = clv(opens[-1], highs[-1], lows[-1], last_price)

    # --- Assembly ---

    return {
        "last": last_price,
        "dma20": dma,
        "support": support,
        "resistance": resistance,
        "rvol": rvol,
        "rs_strength": rs_strength,
        "vwap_diff": vwap_diff,
        "donchian_pos": donchian,
        "avwap_diff": avwap_diff,
        "obv_slope": obv,
        "chaikin_ad": chaikin_ad,
        "clv": last_clv,
        "vwap_confluence": D_ZERO,  # Stubbed
    }
