from __future__ import annotations
from typing import Dict, Any, List, Union

from optipanel.runtime.loop import run_once

class LocalBudget:
    """
    Minimal soft-cap + cooldown backoff model (pure local stub).
    - backoff becomes True when used_lines > soft_cap
    - once over cap, backoff persists for `cooldown` ticks after usage falls back
    """
    def __init__(self, soft_cap: int, cooldown: int):
        self.soft_cap = int(soft_cap)
        self.cooldown = max(0, int(cooldown))
        self._backoff = False
        self._cooldown_left = 0

    @property
    def backoff(self) -> bool:
        return self._backoff

    def step(self, used_lines: int) -> bool:
        used = int(used_lines)
        if used > self.soft_cap:
            # breach -> enter/refresh backoff
            self._backoff = True
            self._cooldown_left = self.cooldown
        else:
            # not over cap: if in backoff, count down cooldown ticks
            if self._backoff:
                if self._cooldown_left > 0:
                    self._cooldown_left -= 1
                if self._cooldown_left == 0:
                    self._backoff = False
        return self._backoff

def _expand_usage(used: Union[int, List[int]], ticks: int) -> List[int]:
    if isinstance(used, int):
        return [used] * ticks
    if not used:
        return [0] * ticks
    if len(used) >= ticks:
        return used[:ticks]
    # pad with last value
    return used + [used[-1]] * (ticks - len(used))

def run_driver(symbols_to_features: Dict[str, Dict[str, Any]],
               profile: Dict[str, Any],
               ticks: int = 5) -> Dict[str, Any]:
    """
    Budget-aware tick driver (pure/offline). Profile keys:
      - soft_cap: int
      - cooldown: int (ticks to remain in backoff after usage drops)
      - used_lines: int or [int,...] length<=ticks (simulated usage)
      - scan_stride_backoff: int (scan every Nth tick while backoff True, default 2)
    Returns:
      {
        "ticks": [
           {"i":0,"used_lines":X,"backoff":bool,"scanned":bool,"run": {...}|None},
           ...
        ],
        "scanned_count": int,
        "backoff_ticks": int
      }
    """
    tmax = max(1, int(ticks))
    soft_cap = int(profile.get("soft_cap", 10))
    cooldown = int(profile.get("cooldown", 2))
    scan_stride = max(1, int(profile.get("scan_stride_backoff", 2)))
    usage_seq = _expand_usage(profile.get("used_lines", 0), tmax)

    budget = LocalBudget(soft_cap=soft_cap, cooldown=cooldown)
    out_ticks: List[Dict[str, Any]] = []
    scanned_count = 0
    backoff_ticks = 0

    for i in range(tmax):
        used = int(usage_seq[i])
        in_backoff = budget.step(used)
        if in_backoff:
            backoff_ticks += 1
            # only scan every Nth tick while in backoff
            do_scan = (i % scan_stride == 0)
        else:
            do_scan = True

        run = run_once(symbols_to_features) if do_scan else None
        if do_scan:
            scanned_count += 1

        out_ticks.append({
            "i": i,
            "used_lines": used,
            "backoff": in_backoff,
            "scanned": do_scan,
            "run": run
        })

    return {"ticks": out_ticks, "scanned_count": scanned_count, "backoff_ticks": backoff_ticks}
