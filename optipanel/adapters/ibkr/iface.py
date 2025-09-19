from __future__ import annotations

from typing import Any, Protocol


class FeaturesProvider(Protocol):
    """
    Contract for a market-data source that can produce our feature dicts.

    features_for_symbols(["AAPL","MSFT"]) -> {
      "AAPL": {"last":..., "dma20":..., "support":..., "resistance":..., "rvol":..., "rs_strength":..., "vwap_diff":...},
      "MSFT": {...}
    }
    """

    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]: ...
