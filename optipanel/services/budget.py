from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BudgetState:
    streams: int = 0
    snapshots_concurrent: int = 0
    rt_bars: int = 0
    backoff_active: bool = False
    last_change_ts: float = 0.0


class BudgetMeter:
    def __init__(self, allowance: int, soft_cap: int, cooldown_sec: int):
        self.allowance = allowance
        self.soft_cap = soft_cap
        self.cooldown = cooldown_sec
        self.state = BudgetState()

    @property
    def used_lines(self) -> int:
        return self.state.streams + self.state.snapshots_concurrent + self.state.rt_bars

    def update(self, *, streams=None, snaps=None, rt_bars=None):
        if streams is not None:
            self.state.streams = streams
        if snaps is not None:
            self.state.snapshots_concurrent = snaps
        if rt_bars is not None:
            self.state.rt_bars = rt_bars
        self.state.last_change_ts = time.time()

    def tick(self) -> None:
        if self.used_lines >= self.soft_cap:
            self.state.backoff_active = True
        else:
            if self.state.backoff_active and (time.time() - self.state.last_change_ts) >= self.cooldown:
                self.state.backoff_active = False
