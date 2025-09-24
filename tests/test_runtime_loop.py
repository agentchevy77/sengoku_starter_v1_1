import json

from optipanel.alerts.engine import DEFAULT_THRESH
from optipanel.cli.main import loop_main
from optipanel.runtime.loop import run_once

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.30,
    "vwap_diff": 0.012,
}
BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 100.0,
    "rvol": 1.5,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
}


def _bundle(last, dma, support, resistance, rvol, rs, *, donchian, obv, ad, clv, avwap, vwap, conf):
    return {
        "last": last,
        "dma20": dma,
        "support": support,
        "resistance": resistance,
        "rvol": rvol,
        "rs_strength": rs,
        "donchian_pos": donchian,
        "obv_slope": obv,
        "chaikin_ad": ad,
        "clv": clv,
        "avwap_diff": avwap,
        "vwap_diff": vwap,
        "vwap_confluence": conf,
    }


ADVANCED_SYMBOLS = {
    "TOP": {
        "last": 112.0,
        "dma20": 102.0,
        "support": 108.0,
        "resistance": 118.0,
        "rvol": 1.8,
        "rs_strength": 0.35,
        "vwap_diff": 0.023,
        "donchian_pos": 0.9,
        "obv_slope": 0.6,
        "chaikin_ad": 0.45,
        "clv": 0.4,
        "avwap_diff": 0.021,
        "vwap_confluence": 0.82,
        "bundles": {
            "15m": _bundle(
                111.5,
                101.0,
                107.5,
                117.0,
                1.7,
                0.32,
                donchian=0.88,
                obv=0.55,
                ad=0.42,
                clv=0.38,
                avwap=0.015,
                vwap=0.018,
                conf=0.8,
            ),
            "60m": _bundle(
                112.0,
                102.0,
                107.0,
                118.5,
                1.85,
                0.36,
                donchian=0.9,
                obv=0.58,
                ad=0.5,
                clv=0.42,
                avwap=0.02,
                vwap=0.022,
                conf=0.83,
            ),
            "1d": _bundle(
                113.0,
                101.5,
                106.5,
                120.0,
                1.9,
                0.4,
                donchian=0.92,
                obv=0.6,
                ad=0.54,
                clv=0.45,
                avwap=0.024,
                vwap=0.026,
                conf=0.85,
            ),
        },
    },
    "LOW": {
        "last": 88.0,
        "dma20": 96.0,
        "support": 90.0,
        "resistance": 95.0,
        "rvol": 0.75,
        "rs_strength": -0.28,
        "vwap_diff": -0.03,
        "donchian_pos": 0.18,
        "obv_slope": -0.5,
        "chaikin_ad": -0.42,
        "clv": -0.35,
        "avwap_diff": -0.022,
        "vwap_confluence": 0.6,
        "bundles": {
            "15m": _bundle(
                87.5,
                95.5,
                89.0,
                94.5,
                0.72,
                -0.22,
                donchian=0.2,
                obv=-0.45,
                ad=-0.38,
                clv=-0.3,
                avwap=-0.018,
                vwap=-0.02,
                conf=0.58,
            ),
            "60m": _bundle(
                88.0,
                95.0,
                89.5,
                95.5,
                0.74,
                -0.3,
                donchian=0.18,
                obv=-0.5,
                ad=-0.4,
                clv=-0.34,
                avwap=-0.02,
                vwap=-0.024,
                conf=0.6,
            ),
            "1d": _bundle(
                88.2,
                94.0,
                90.0,
                96.0,
                0.78,
                -0.32,
                donchian=0.16,
                obv=-0.55,
                ad=-0.45,
                clv=-0.36,
                avwap=-0.024,
                vwap=-0.028,
                conf=0.62,
            ),
        },
    },
}


def test_run_once_has_scan_and_alerts():
    out = run_once({"AAA": BULL, "BBB": BEAR})
    assert "scan" in out and "alerts" in out
    assert isinstance(out["scan"], dict)
    assert isinstance(out["scan"]["results"], list)
    assert isinstance(out["alerts"], list)
    # sanity: both symbols represented somewhere in output
    syms_scan = {r["symbol"] for r in out["scan"]["results"]}
    syms_alert = {a["symbol"] for a in out["alerts"]}
    assert {"AAA", "BBB"} & syms_scan
    assert {"AAA", "BBB"} <= (syms_scan | syms_alert)


def test_loop_main_json(capsys):
    payload = json.dumps({"AAA": BULL, "BBB": BEAR})
    rc = loop_main(["--symbols-json", payload, "--iterations", "2", "--sleep", "0"])
    assert rc == 0
    text = capsys.readouterr().out
    data = json.loads(text)
    assert data["iterations"] == 2
    assert "runs" in data and len(data["runs"]) == 2
    # each run has scan+alerts
    for r in data["runs"]:
        assert "scan" in r and "alerts" in r
        assert isinstance(r["scan"]["results"], list)


def test_run_once_integration_chip_summary_and_alerts():
    out = run_once(ADVANCED_SYMBOLS)

    scan = out["scan"]
    results = scan["results"]
    assert {r["symbol"] for r in results} == set(ADVANCED_SYMBOLS)

    counts_total = sum(scan["advice_counts"].values())
    assert counts_total == len(results)

    result_by_symbol = {r["symbol"]: r for r in results}
    top_symbol = scan["top"][0]
    top_snapshot = result_by_symbol[top_symbol]

    chips = top_snapshot["prob_chips"]
    tf_keys = [key for key in chips if key != "summary"]
    assert tf_keys
    for chip_name in chips["summary"]:
        expected = round(sum(chips[tf][chip_name] for tf in tf_keys) / len(tf_keys))
        assert chips["summary"][chip_name] == expected

    attack_thresh = DEFAULT_THRESH["score_attack"]
    defend_thresh = DEFAULT_THRESH["score_defend"]

    if top_snapshot["score"] >= attack_thresh:
        assert any(alert["symbol"] == top_symbol and alert["kind"] == "score_attack" for alert in out["alerts"])

    low_snapshot = result_by_symbol[[s for s in result_by_symbol if s != top_symbol][0]]
    if low_snapshot["score"] <= defend_thresh:
        assert any(
            alert["symbol"] == low_snapshot["symbol"] and alert["kind"] == "score_defend" for alert in out["alerts"]
        )

    assert out["panels"]["features_top"] == ADVANCED_SYMBOLS[top_symbol]
