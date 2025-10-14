# TWS Fetcher Refactoring: After-Action Report & Path Forward

## 1. Executive Summary

The previous TWS fetcher implementation (`AsyncTwsFetcher`, referred to as v2) was determined to be the root cause of significant instability, including application hangs and `TimeoutError` exceptions during live tests. The design, which relied on a stateful, multi-threaded background process for connection management, proved overly complex and difficult to debug.

A full investigation revealed two core problems:
1.  **Flawed Design:** The complexity of the background heartbeat and reconnection logic led to deadlocks and unhandled edge cases.
2.  **Dependency Mismatch:** A critical discovery was made that the project was using the `ib_insync` library while the `pyproject.toml` manifest incorrectly specified `ibapi`. This lack of proper dependency management contributed to the instability.

The v2 fetcher has been abandoned. A new, simplified, stateless fetcher (`TwsFetcherV3`, a.k.a. "The Sledgehammer") was designed, implemented, and successfully tested. This report details the final, recommended implementation and the necessary corrections to the project's dependency manifest.

**Recommendation:** The `TwsFetcherV3` implementation should be adopted as the standard for all TWS data fetching operations going forward. All previous fetcher code should be deprecated and removed.

---

## 2. `TwsFetcherV3` (Sledgehammer) Final Implementation

The recommended solution is a stateless fetcher that connects, fetches, and disconnects in a single, atomic, and easily understandable operation. This eliminates all background tasks and complex state management.

**File:** `optipanel/adapters/ibkr/tws_fetcher_v3.py`

```python
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ib_insync import IB, Stock, Contract, BarData

@dataclass
class TwsSledgehammerConfig:
    """Configuration for the TwsFetcherV3 Sledgehammer."""
    host: str = "192.168.80.1"
    port: int = 7496
    client_id: int = 107
    request_timeout_sec: float = 45.0

@dataclass
class Result:
    """Represents the outcome of an operation for a single symbol."""
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None

    @property
    def success(self) -> bool:
        return self.error is None

class TwsFetcherV3:
    """
    The Sledgehammer: A simple, stateless TWS fetcher.
    It connects, fetches, and disconnects in a single, atomic operation.
    """
    def __init__(self, config: TwsSledgehammerConfig):
        self.config = config
        logging.info(f"TwsFetcherV3 (Sledgehammer) initialized for {config.host}:{config.port}")

    async def fetch_features(self, symbols: List[str]) -> Dict[str, Result]:
        """
        The single public method. Connects, fetches data for all symbols,
        and disconnects. This is an atomic operation.
        """
        ib = IB()
        results: Dict[str, Result] = {}

        try:
            await ib.connectAsync(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.request_timeout_sec,
            )

            unique_symbols = list(dict.fromkeys(symbols))
            contracts = await self._get_contracts(ib, unique_symbols)

            tasks = []
            for symbol in unique_symbols:
                if symbol in contracts:
                    tasks.append(self._fetch_one(ib, contracts[symbol]))
                else:
                    results[symbol] = Result(error=ValueError(f"Could not qualify contract for {symbol}."))
            
            fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

            valid_symbols_index = 0
            for symbol in unique_symbols:
                if symbol in contracts:
                    res = fetch_results[valid_symbols_index]
                    if isinstance(res, Exception):
                        results[symbol] = Result(error=res)
                    else:
                        results[symbol] = Result(data=res)
                    valid_symbols_index += 1

            final_results = {s: results[s] for s in symbols}
            return final_results

        except Exception as e:
            logging.error(f"Sledgehammer strike failed: {e}", exc_info=True)
            return {s: Result(error=e) for s in symbols}

        finally:
            if ib.isConnected():
                ib.disconnect()

    async def _get_contracts(self, ib: IB, symbols: List[str]) -> Dict[str, Contract]:
        contracts = {}
        reqs = [Stock(s, "SMART", "USD") for s in symbols]
        qualified_contracts = await ib.qualifyContractsAsync(*reqs)
        for qc in qualified_contracts:
            if qc.conId:
                contracts[qc.symbol] = qc
        return contracts

    async def _fetch_one(self, ib: IB, contract: Contract) -> Dict[str, Any]:
        bars = await ib.reqHistoricalDataAsync(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES", useRTH=True,
        )
        if not bars:
            raise ValueError(f"No historical data for {contract.symbol}")
        return self._calculate_features(bars)

    def _calculate_features(self, bars: List[BarData]) -> Dict[str, Any]:
        MIN_BARS = 20
        if len(bars) < MIN_BARS:
            raise ValueError(f"Insufficient data (Required {MIN_BARS}, Got {len(bars)}).")
        last_price = bars[-1].close
        dma20_bars = bars[-MIN_BARS:]
        dma20 = sum(b.close for b in dma20_bars) / MIN_BARS
        return {"last": last_price, "dma20": dma20}
```

---

## 3. Dependency Manifest Correction (`pyproject.toml`)

To resolve the dependency mismatch, the following changes were made to `pyproject.toml`.

**1. Removal of `ibapi` from `[project.optional-dependencies]`:**

```diff
-[project.optional-dependencies]
-ibkr = ["ibapi>=10.19.1"]
```

**2. Addition of `ib_insync` to core `[project]` dependencies:**

```diff
 [project]
 name = "optipanel-sengoku"
 version = "0.7.0"
 description = "Sengoku Decision Cockpit — starter scaffold (memory-safe)"
 requires-python = ">=3.11"
 dependencies = [
     "packaging>=25.0",
     "pyyaml>=6.0.2",
     "orjson>=3.10.0",
+    "ib_insync>=0.9.80",
 ]
```

These changes ensure that the project now correctly declares and installs the library that the code actually uses. This was verified by running `.venv/bin/pip install -e .` and confirming the successful installation of `ib_insync`.
