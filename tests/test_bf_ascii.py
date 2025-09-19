from optipanel.battlefield.ascii import render_battlefield
from optipanel.battlefield.engine import compute_units

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


def _line_for(label: str, s: str) -> str:
    t = label.lower()
    for line in s.splitlines():
        if line.strip().lower().startswith(t):
            return line
    raise AssertionError(f"missing line for {label}")


def _hash_count(line: str, which: str) -> int:
    # e.g. "... bull [####......]  bear [###.......]"
    import re

    m = re.search(rf"{which}\s*\[([#\.]+)\]", line, flags=re.I)
    assert m, f"{which} segment not found in: {line}"
    return m.group(1).count("#")


def test_ascii_contains_key_units_and_summary():
    u = compute_units(BULL)
    s = render_battlefield(u, width=20)
    for name in ("dma20", "support", "resistance", "rvol", "rs"):
        assert name in s.lower()
    assert "total" in s.lower()


def test_ascii_dma20_bar_trends_correctly():
    s1 = render_battlefield(compute_units(BULL), width=20)
    s2 = render_battlefield(compute_units(BEAR), width=20)
    l1 = _line_for("dma20", s1)
    l2 = _line_for("dma20", s2)
    assert _hash_count(l1, "bull") > _hash_count(l1, "bear")  # above DMA -> bull dom
    assert _hash_count(l2, "bear") > _hash_count(l2, "bull")  # below DMA -> bear dom
