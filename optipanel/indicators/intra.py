"""Intraday indicator helpers and feature bundle assembly."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

_EPS = 1e-9


def _clip(value: float, lower: float, upper: float) -> float:
    """Clamp *value* into the inclusive range [lower, upper]."""
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _as_sequence(values: Iterable[float]) -> list[float]:
    if isinstance(values, Sequence):
        return list(values)
    return list(values)


def donchian_pos(highs: Iterable[float], lows: Iterable[float], close: float) -> float:
    """Return position of *close* within the high/low channel as 0..1."""
    highs_list = _as_sequence(highs)
    lows_list = _as_sequence(lows)
    if not highs_list or not lows_list:
        return 0.5
    hi = max(highs_list)
    lo = min(lows_list)
    span = hi - lo
    if span <= 0:
        return 0.5
    return _clip((close - lo) / span, 0.0, 1.0)


def clv(open_: float, high: float, low: float, close: float) -> float:
    """Close Location Value scaled to [-1, 1]; graceful on degenerate bars."""
    span = high - low
    if span <= 0:
        return 0.0
    value = ((close - low) - (high - close)) / span
    return _clip(value, -1.0, 1.0)


def _normalized_slope(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    start = values[0]
    end = values[-1]
    diff = end - start
    scale = max(abs(max(values)), abs(min(values)), abs(diff), 1.0)
    return _clip(diff / (scale + _EPS), -1.0, 1.0)


def obv_slope(closes: Iterable[float], volumes: Iterable[float], window: int = 20) -> float:
    """On-Balance Volume slope normalised to [-1, 1]."""
    close_list = _as_sequence(closes)
    volume_list = _as_sequence(volumes)
    n = min(len(close_list), len(volume_list))
    if n < 2:
        return 0.0
    obv: list[float] = [0.0]
    for idx in range(1, n):
        prev_close = close_list[idx - 1]
        cur_close = close_list[idx]
        delta = volume_list[idx]
        if cur_close > prev_close:
            obv.append(obv[-1] + delta)
        elif cur_close < prev_close:
            obv.append(obv[-1] - delta)
        else:
            obv.append(obv[-1])
    span = min(window, len(obv) - 1)
    return _normalized_slope(obv[-(span + 1) :])


def chaikin_ad_slope(
    highs: Iterable[float],
    lows: Iterable[float],
    closes: Iterable[float],
    volumes: Iterable[float],
    window: int = 20,
) -> float:
    """Chaikin Accumulation/Distribution slope normalised to [-1, 1]."""
    high_list = _as_sequence(highs)
    low_list = _as_sequence(lows)
    close_list = _as_sequence(closes)
    volume_list = _as_sequence(volumes)
    n = min(len(high_list), len(low_list), len(close_list), len(volume_list))
    if n < 1:
        return 0.0
    ad: list[float] = [0.0]
    for idx in range(n):
        high = high_list[idx]
        low = low_list[idx]
        close = close_list[idx]
        volume = volume_list[idx]
        spread = high - low
        money_flow = 0.0 if spread <= 0 else (close - low - (high - close)) / spread
        ad.append(ad[-1] + money_flow * volume)
    if len(ad) < 2:
        return 0.0
    span = min(window, len(ad) - 1)
    return _normalized_slope(ad[-(span + 1) :])


def rvol_ratio(volumes: Iterable[float], recent: int = 20, baseline: int = 60) -> float:
    """Return recent-average / baseline-average volume ratio."""
    volume_list = _as_sequence(volumes)
    n = len(volume_list)
    if n < max(recent, baseline) or recent <= 0:
        return 1.0
    recent = min(recent, n)
    baseline = min(baseline, n)
    if baseline <= recent:
        baseline = min(n, recent + max(1, recent // 2))
    recent_slice = volume_list[-recent:]
    baseline_slice = volume_list[-baseline:-recent]
    if not baseline_slice:
        return 1.0
    recent_avg = sum(recent_slice) / len(recent_slice)
    baseline_avg = sum(baseline_slice) / len(baseline_slice)
    if baseline_avg <= 0:
        return 1.0
    return max(0.0, recent_avg / baseline_avg)


def _calculate_relative_strength(
    closes: Sequence[float],
    benchmark_closes: Sequence[float],
    window: int,
) -> float:
    """Calculate the performance difference between a stock and a benchmark."""
    if not closes or not benchmark_closes or window <= 0:
        return 0.0

    lookback = min(window, len(closes), len(benchmark_closes))
    if lookback < 2:
        return 0.0

    start_price = closes[-lookback]
    end_price = closes[-1]

    start_benchmark = benchmark_closes[-lookback]
    end_benchmark = benchmark_closes[-1]

    if start_price <= 0 or start_benchmark <= 0:
        return 0.0

    stock_perf = (end_price - start_price) / start_price
    bench_perf = (end_benchmark - start_benchmark) / start_benchmark

    return stock_perf - bench_perf


def assemble_features_from_bars(
    bars: Sequence[dict[str, float]],
    benchmark_bars: Sequence[dict[str, float]] | None = None,
    window: int = 20,
) -> dict[str, float]:
    """Assemble a feature bundle from OHLCV bars using safe defaults."""
    if not bars:
        return {
            "last": 0.0,
            "dma20": 0.0,
            "support": 0.0,
            "resistance": 0.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
            "vwap_diff": 0.0,
            "donchian_pos": 0.5,
            "avwap_diff": 0.0,
            "obv_slope": 0.0,
            "chaikin_ad": 0.0,
            "clv": 0.0,
            "vwap_confluence": 0.0,
        }

    closes = [float(bar["c"]) for bar in bars]
    highs = [float(bar["h"]) for bar in bars]
    lows = [float(bar["l"]) for bar in bars]
    opens = [float(bar["o"]) for bar in bars]
    volumes = [float(bar.get("v", 0.0)) for bar in bars]

    benchmark_closes = [float(bar["c"]) for bar in benchmark_bars] if benchmark_bars else []

    lookback = min(window, len(bars))
    closes_win = closes[-lookback:]
    highs_win = highs[-lookback:]
    lows_win = lows[-lookback:]

    dma = sum(closes_win) / len(closes_win)
    recent_vol_window = min(20, len(volumes))
    baseline_window = min(60, len(volumes))

    rs_strength = _calculate_relative_strength(closes, benchmark_closes, lookback)

    return {
        "last": closes[-1],
        "dma20": dma,
        "support": min(lows_win),
        "resistance": max(highs_win),
        "rvol": rvol_ratio(volumes, recent=recent_vol_window, baseline=baseline_window) if volumes else 1.0,
        "rs_strength": rs_strength,
        "vwap_diff": 0.0,
        "donchian_pos": donchian_pos(highs_win, lows_win, closes[-1]),
        "avwap_diff": 0.0,
        "obv_slope": obv_slope(closes, volumes, window=min(20, len(closes))) if volumes else 0.0,
        "chaikin_ad": chaikin_ad_slope(highs, lows, closes, volumes, window=min(20, len(closes))) if volumes else 0.0,
        "clv": clv(opens[-1], highs[-1], lows[-1], closes[-1]),
        "vwap_confluence": 0.0,
    }
