from __future__ import annotations

from typing import Any, Protocol


class MarketAdapter(Protocol):
    async def get_underlying_snapshot(self, symbol: str) -> dict[str, Any]: ...
    async def get_option_chain_slice(self, symbol: str) -> dict[str, Any]: ...
