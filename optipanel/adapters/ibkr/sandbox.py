from __future__ import annotations

import random
import time


class SandboxAdapter:
    def __init__(self, seed: int = 7):
        self._rng = random.Random(seed)

    async def get_underlying_snapshot(self, symbol: str):
        px = round(100 + self._rng.uniform(-1, 1), 2)
        return {"symbol": symbol, "last": px, "as_of": time.time()}

    async def get_option_chain_slice(self, symbol: str):
        mid = round(2 + self._rng.uniform(-0.2, 0.2), 2)
        return {"symbol": symbol, "atm": {"call": mid, "put": mid}, "as_of": time.time()}
