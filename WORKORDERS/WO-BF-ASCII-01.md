# WO-BF-ASCII-01 — ASCII battlefield renderer (pure, no I/O)

**Status: COMPLETE**

**Allowed paths**
- `optipanel/battlefield/ascii.py`
- `optipanel/battlefield/__init__.py` (export symbol only)

**Do NOT modify tests** (`tests/test_bf_ascii.py`).

## Task
Implement:
```python
def render_battlefield(units: dict, width: int = 20) -> str:
    """
    Returns a multi-line ASCII string, one line per indicator:
      <name>  bull [####......]  bear [###.......]
    Also add a TOP summary line "TOTAL bull [..] bear [..]" using the
    sum of bull/bear intensities across all indicators.
    Deterministic, pure; no I/O; no ANSI colors.
    """

cd ~/sengoku_starter_v1_1
source .venv/bin/activate

# Keep __init__.py exporting render_battlefield (Claude already did that).
# Replace ascii.py with the bar renderer that tests expect.
cat > optipanel/battlefield/ascii.py << 'EOF'
from __future__ import annotations
from typing import Dict, Any, Iterable

# Preferred display order; any extra keys will be appended alphabetically.
ORDER = ["dma20","support","resistance","rvol","rs"]

def _bar(val: int, width: int) -> str:
    try:
        v = int(val)
    except Exception:
        v = 0
    v = 0 if v < 0 else 100 if v > 100 else v
    n = max(0, min(width, round(v * width / 100)))
    return "#" * n + "." * (width - n)

def _sorted_keys(d: Dict[str, Any]) -> Iterable[str]:
    seen = set()
    for k in ORDER:
        if k in d:
            seen.add(k)
            yield k
    for k in sorted(d.keys()):
        if k not in seen:
            yield k

def render_battlefield(units: Dict[str, Dict[str, int]], width: int = 20) -> str:
    """
    Multi-line ASCII battlefield:
      <name>      bull [####......]  bear [###.......]
    + top summary TOTAL line using average intensities across indicators.
    Pure, deterministic; no I/O; no colors.
    """
    if not isinstance(units, dict) or not units:
        return f"TOTAL      bull [{_bar(0, width)}]  bear [{_bar(0, width)}]"

    count = 0
    bull_sum = 0
    bear_sum = 0
    for v in units.values():
        if isinstance(v, dict):
            bull_sum += int(v.get("bull", 0))
            bear_sum += int(v.get("bear", 0))
            count += 1
    count = max(1, count)
    bull_avg = round(bull_sum / count)
    bear_avg = round(bear_sum / count)

    lines = []
    lines.append(f"TOTAL      bull [{_bar(bull_avg, width)}]  bear [{_bar(bear_avg, width)}]")

    for k in _sorted_keys(units):
        v = units.get(k, {})
        bull = int(v.get("bull", 0)) if isinstance(v, dict) else 0
        bear = int(v.get("bear", 0)) if isinstance(v, dict) else 0
        lines.append(f"{k:<10} bull [{_bar(bull, width)}]  bear [{_bar(bear, width)}]")

    return "\n".join(lines)

**Primary test:** `pytest tests/test_bf_ascii.py -q`
