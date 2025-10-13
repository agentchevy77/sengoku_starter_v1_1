import pytest

from optipanel.indicators.intra import (
    assemble_features_from_bars,
    chaikin_ad_slope,
    clv,
    donchian_pos,
    obv_slope,
    rvol_ratio,
)


def test_donchian_and_clv_basic():
    highs = [10.0, 11.0, 12.0]
    lows = [8.0, 9.0, 10.0]
    close = 11.9
    assert 0.8 < donchian_pos(highs, lows, close) <= 1.0
    assert clv(9.5, 12.0, 8.0, 11.8) > 0.5


def test_slopes_trend_up():
    closes = [10.0, 10.2, 10.6, 11.1, 11.8]
    volumes = [100, 120, 140, 160, 180]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.8 for c in closes]
    assert obv_slope(closes, volumes) > 0.0
    assert chaikin_ad_slope(highs, lows, closes, volumes) > 0.0


def test_slopes_trend_down():
    closes = [12.0, 11.5, 11.0, 10.6, 10.2]
    volumes = [200, 190, 180, 170, 160]
    highs = [c + 0.8 for c in closes]
    lows = [c - 0.3 for c in closes]
    assert obv_slope(closes, volumes) < 0.0
    assert chaikin_ad_slope(highs, lows, closes, volumes) < 0.0


def test_rvol_ratio_behaviour():
    vols = [100.0] * 80
    vols[-20:] = [180.0] * 20
    ratio = rvol_ratio(vols, recent=20, baseline=60)
    assert ratio > 1.0


def test_assemble_features_from_bars_defaults_and_keys():
    empty_bundle = assemble_features_from_bars([], benchmark_bars=None)
    assert empty_bundle["rvol"] == 1.0
    assert empty_bundle["rs_strength"] == 0.0
    bars = [
        {"o": 10.0, "h": 10.5, "l": 9.8, "c": 10.1, "v": 100.0},
        {"o": 10.2, "h": 10.9, "l": 10.1, "c": 10.8, "v": 120.0},
        {"o": 10.8, "h": 11.4, "l": 10.4, "c": 11.3, "v": 160.0},
    ]
    bundle = assemble_features_from_bars(bars, benchmark_bars=None, window=2)
    required = {
        "last",
        "dma20",
        "support",
        "resistance",
        "rvol",
        "donchian_pos",
        "obv_slope",
        "chaikin_ad",
        "clv",
        "rs_strength",
    }
    assert required.issubset(bundle.keys())
    assert bundle["last"] == bars[-1]["c"]
    assert 0.0 <= bundle["donchian_pos"] <= 1.0
    assert bundle["rs_strength"] == 0.0


RECORDED_BARS = [
    {"o": 429.85, "h": 431.70, "l": 428.90, "c": 431.10, "v": 18_250_000},
    {"o": 431.20, "h": 432.55, "l": 429.75, "c": 431.48, "v": 17_430_000},
    {"o": 431.60, "h": 433.10, "l": 430.05, "c": 432.72, "v": 19_180_000},
    {"o": 432.90, "h": 434.25, "l": 431.80, "c": 433.95, "v": 20_040_000},
    {"o": 433.80, "h": 435.35, "l": 433.10, "c": 434.88, "v": 21_120_000},
    {"o": 435.10, "h": 436.40, "l": 434.00, "c": 435.72, "v": 19_880_000},
    {"o": 435.40, "h": 436.95, "l": 434.60, "c": 436.84, "v": 18_760_000},
    {"o": 437.10, "h": 438.60, "l": 436.35, "c": 438.12, "v": 20_610_000},
    {"o": 438.40, "h": 439.20, "l": 437.25, "c": 438.75, "v": 18_950_000},
    {"o": 438.90, "h": 440.05, "l": 437.80, "c": 439.52, "v": 21_330_000},
    {"o": 440.20, "h": 441.55, "l": 439.30, "c": 441.10, "v": 22_480_000},
    {"o": 441.45, "h": 442.35, "l": 440.05, "c": 441.92, "v": 20_420_000},
    {"o": 441.80, "h": 443.00, "l": 441.10, "c": 442.65, "v": 19_870_000},
    {"o": 443.10, "h": 444.30, "l": 442.35, "c": 443.88, "v": 23_120_000},
    {"o": 444.00, "h": 445.40, "l": 443.20, "c": 444.95, "v": 24_050_000},
    {"o": 445.60, "h": 446.80, "l": 444.75, "c": 446.30, "v": 21_760_000},
    {"o": 446.20, "h": 447.55, "l": 445.10, "c": 446.92, "v": 20_840_000},
    {"o": 447.10, "h": 448.40, "l": 445.95, "c": 447.55, "v": 19_930_000},
    {"o": 447.00, "h": 448.05, "l": 445.60, "c": 446.18, "v": 22_120_000},
    {"o": 446.40, "h": 447.35, "l": 444.95, "c": 445.50, "v": 21_580_000},
    {"o": 445.30, "h": 446.25, "l": 443.85, "c": 444.70, "v": 20_740_000},
    {"o": 444.50, "h": 445.80, "l": 443.60, "c": 445.18, "v": 19_920_000},
    {"o": 445.05, "h": 446.55, "l": 443.85, "c": 444.02, "v": 18_660_000},
    {"o": 443.70, "h": 444.90, "l": 442.65, "c": 444.55, "v": 17_980_000},
    {"o": 444.60, "h": 446.10, "l": 443.50, "c": 445.92, "v": 18_540_000},
]


def test_realistic_series_features_have_expected_profile():
    bundle = assemble_features_from_bars(RECORDED_BARS, benchmark_bars=None, window=20)
    closes = [b["c"] for b in RECORDED_BARS[-20:]]
    highs = [b["h"] for b in RECORDED_BARS[-20:]]
    lows = [b["l"] for b in RECORDED_BARS[-20:]]
    volumes = [b["v"] for b in RECORDED_BARS]

    expected_dma = sum(closes) / len(closes)
    expected_support = min(lows)
    expected_resistance = max(highs)

    assert bundle["last"] == pytest.approx(RECORDED_BARS[-1]["c"])
    assert bundle["dma20"] == pytest.approx(expected_dma, rel=1e-6)
    assert bundle["support"] == pytest.approx(expected_support)
    assert bundle["resistance"] == pytest.approx(expected_resistance)
    assert 0.0 <= bundle["donchian_pos"] <= 1.0
    assert bundle["obv_slope"] != 0.0
    assert bundle["chaikin_ad"] != 0.0
    assert bundle["clv"] != 0.0
    assert bundle["rvol"] == pytest.approx(
        rvol_ratio(volumes, recent=min(20, len(volumes)), baseline=min(60, len(volumes)))
    )
    assert bundle["rs_strength"] == 0.0


def test_rs_strength_calculation():
    stock_bars_outperform = [
        {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000.0},
        {"o": 110.0, "h": 111.0, "l": 109.0, "c": 110.0, "v": 1_100.0},
    ]
    benchmark_bars_outperform = [
        {"o": 100.0, "h": 100.5, "l": 99.5, "c": 100.0, "v": 1_000.0},
        {"o": 105.0, "h": 105.5, "l": 104.5, "c": 105.0, "v": 1_050.0},
    ]
    bundle = assemble_features_from_bars(
        stock_bars_outperform,
        benchmark_bars=benchmark_bars_outperform,
        window=2,
    )
    assert bundle["rs_strength"] == pytest.approx(0.05)

    stock_bars_relatively_stronger = [
        {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000.0},
        {"o": 90.0, "h": 91.0, "l": 89.0, "c": 90.0, "v": 900.0},
    ]
    benchmark_bars_relatively_weaker = [
        {"o": 100.0, "h": 100.5, "l": 99.5, "c": 100.0, "v": 1_000.0},
        {"o": 80.0, "h": 80.5, "l": 79.5, "c": 80.0, "v": 800.0},
    ]
    bundle = assemble_features_from_bars(
        stock_bars_relatively_stronger,
        benchmark_bars=benchmark_bars_relatively_weaker,
        window=2,
    )
    assert bundle["rs_strength"] == pytest.approx(0.10)

    stock_bars_underperform = [
        {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000.0},
        {"o": 105.0, "h": 106.0, "l": 104.0, "c": 105.0, "v": 1_050.0},
    ]
    benchmark_bars_outperform = [
        {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000.0},
        {"o": 110.0, "h": 111.0, "l": 109.0, "c": 110.0, "v": 1_100.0},
    ]
    bundle = assemble_features_from_bars(
        stock_bars_underperform,
        benchmark_bars=benchmark_bars_outperform,
        window=2,
    )
    assert bundle["rs_strength"] == pytest.approx(-0.05)

    # Missing benchmark data should leave the signal neutral.
    bundle = assemble_features_from_bars(stock_bars_outperform, benchmark_bars=None, window=2)
    assert bundle["rs_strength"] == 0.0
