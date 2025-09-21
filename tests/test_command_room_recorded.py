from optipanel.runtime.loop import run_once
from optipanel.ui.command_room import render_command_room

RECORDED_FEED = {
    "ALPHA": {
        "last": 305.4,
        "dma20": 301.2,
        "support": 299.5,
        "resistance": 308.1,
        "rvol": 1.35,
        "rs_strength": 0.22,
        "vwap_diff": 0.008,
        "bundles": {
            "15m": {
                "last": 304.8,
                "dma20": 302.1,
                "support": 300.0,
                "resistance": 306.4,
                "rvol": 1.28,
                "rs_strength": 0.19,
                "vwap_diff": 0.007,
                "donchian_pos": 0.84,
                "obv_slope": 0.52,
                "chaikin_ad": 0.48,
                "clv": 0.44,
                "avwap_diff": 0.013,
                "vwap_confluence": 0.61,
            },
            "60m": {
                "last": 305.1,
                "dma20": 301.0,
                "support": 299.8,
                "resistance": 307.2,
                "rvol": 1.20,
                "rs_strength": 0.16,
                "vwap_diff": 0.006,
                "donchian_pos": 0.76,
                "obv_slope": 0.46,
                "chaikin_ad": 0.41,
                "clv": 0.39,
                "avwap_diff": 0.010,
                "vwap_confluence": 0.58,
            },
            "1d": {
                "last": 305.4,
                "dma20": 301.2,
                "support": 299.5,
                "resistance": 308.1,
                "rvol": 1.35,
                "rs_strength": 0.22,
                "vwap_diff": 0.008,
                "donchian_pos": 0.88,
                "obv_slope": 0.60,
                "chaikin_ad": 0.55,
                "clv": 0.49,
                "avwap_diff": 0.016,
                "vwap_confluence": 0.68,
            },
        },
    },
    "BETA": {
        "last": 92.8,
        "dma20": 96.4,
        "support": 91.5,
        "resistance": 97.2,
        "rvol": 0.82,
        "rs_strength": -0.18,
        "vwap_diff": -0.009,
        "bundles": {
            "15m": {
                "last": 92.6,
                "dma20": 95.8,
                "support": 91.2,
                "resistance": 94.9,
                "rvol": 0.78,
                "rs_strength": -0.21,
                "vwap_diff": -0.010,
                "donchian_pos": 0.18,
                "obv_slope": -0.46,
                "chaikin_ad": -0.42,
                "clv": -0.40,
                "avwap_diff": -0.015,
                "vwap_confluence": 0.35,
            },
            "60m": {
                "last": 92.9,
                "dma20": 96.0,
                "support": 91.0,
                "resistance": 95.8,
                "rvol": 0.85,
                "rs_strength": -0.16,
                "vwap_diff": -0.008,
                "donchian_pos": 0.22,
                "obv_slope": -0.38,
                "chaikin_ad": -0.34,
                "clv": -0.31,
                "avwap_diff": -0.011,
                "vwap_confluence": 0.38,
            },
            "1d": {
                "last": 92.8,
                "dma20": 96.4,
                "support": 91.5,
                "resistance": 97.2,
                "rvol": 0.82,
                "rs_strength": -0.18,
                "vwap_diff": -0.009,
                "donchian_pos": 0.20,
                "obv_slope": -0.44,
                "chaikin_ad": -0.41,
                "clv": -0.37,
                "avwap_diff": -0.013,
                "vwap_confluence": 0.36,
            },
        },
    },
}


def test_command_room_handles_recorded_multi_tf_feed():
    run_out = run_once(RECORDED_FEED)
    panel = render_command_room(run_out, width=18, top_n=2)
    lower = panel.lower()
    assert "chips(summary)" in lower
    assert "chips(15m)" in lower
    assert "chips(60m)" in lower
    assert "chips(1d)" in lower
    assert "donchian" in lower and "avwap" in lower
    assert "scout     recon" in lower
