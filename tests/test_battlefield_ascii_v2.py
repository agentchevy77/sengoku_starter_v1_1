from optipanel.battlefield.ascii import render_battlefield_from_bundle

BULL = {
    "last": 105.0,
    "dma20": 100.0,
    "support": 101.0,
    "resistance": 106.0,
    "rvol": 1.6,
    "rs_strength": 0.25,
    "vwap_diff": 0.012,
    "donchian_pos": 0.9,
    "avwap_diff": 0.02,
    "obv_slope": 0.7,
    "chaikin_ad": 0.55,
    "clv": 0.6,
    "vwap_confluence": 0.6,
}

BEAR = {
    "last": 95.0,
    "dma20": 100.0,
    "support": 96.0,
    "resistance": 99.0,
    "rvol": 0.85,
    "rs_strength": -0.25,
    "vwap_diff": -0.012,
    "donchian_pos": 0.1,
    "avwap_diff": -0.02,
    "obv_slope": -0.7,
    "chaikin_ad": -0.5,
    "clv": -0.6,
    "vwap_confluence": 0.4,
}


def _line_for(label: str, text: str) -> str:
    target = label.lower()
    for line in text.splitlines():
        if line.strip().lower().startswith(target):
            return line
    raise AssertionError(f"missing line for {label}")


def _hash_count(line: str, which: str) -> int:
    import re

    pattern = re.compile(rf"{re.escape(which)}\s*\[([#.]+)\]", flags=re.I)
    match = pattern.search(line)
    assert match, f"{which} segment not found in: {line}"
    return match.group(1).count("#")


def test_render_bundle_contains_all_units():
    output = render_battlefield_from_bundle(BULL, width=16)
    keys = ("dma20", "support", "resistance", "rvol", "rs", "donchian", "obv", "ad", "clv", "avwap")
    for key in keys:
        assert key in output.lower()
    assert output.splitlines()[0].lower().startswith("total")


def test_render_bundle_directional_signals():
    bull_output = render_battlefield_from_bundle(BULL, width=20)
    bear_output = render_battlefield_from_bundle(BEAR, width=20)

    bull_don = _line_for("donchian", bull_output)
    bear_don = _line_for("donchian", bear_output)
    assert _hash_count(bull_don, "bull") > _hash_count(bear_don, "bull")

    bull_res = _line_for("resistance", bull_output)
    bear_res = _line_for("resistance", bear_output)
    assert _hash_count(bull_res, "bear") > _hash_count(bear_res, "bear")
    assert _hash_count(bull_res, "bull") < _hash_count(bear_res, "bull")

    bull_avwap = _line_for("avwap", bull_output)
    bear_avwap = _line_for("avwap", bear_output)
    assert _hash_count(bull_avwap, "bull") > _hash_count(bear_avwap, "bull")
