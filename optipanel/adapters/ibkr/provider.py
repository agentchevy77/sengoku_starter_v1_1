from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class TwsFeaturesProvider:
    """
    Façade that orchestrates fetching, benchmark injection, and translation.
    Exposes a single features_for_symbols(symbols) method used by the runtime.
    """

    def __init__(
        self,
        # Fetcher signature expectation: Callable[[list[str]], dict[str, dict[str, Any]]]
        fetcher: Callable[..., dict[str, dict[str, Any]]],
        # Translator signature expectation: Callable[..., dict[str, dict[str, Any]]]
        # (We expect it to accept benchmark_symbol keyword argument)
        translator: Callable[..., dict[str, dict[str, Any]]],
        benchmark_symbol: str | None = "SPY",  # Default benchmark
    ):
        self.fetcher = fetcher
        self.translator = translator
        self.benchmark_symbol = benchmark_symbol
        if benchmark_symbol:
            logger.info("TwsFeaturesProvider initialized with benchmark symbol: %s", benchmark_symbol)

    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:

        # 1. Determine symbols to fetch (ensure uniqueness and include benchmark)
        # Convert input symbols to a set for efficient management
        requested_symbols = set(symbols)
        symbols_to_fetch = list(requested_symbols)

        if self.benchmark_symbol and self.benchmark_symbol not in requested_symbols:
            symbols_to_fetch.append(self.benchmark_symbol)

        # 2. Fetch raw data
        try:
            # We assume the fetcher accepts a list of strings.
            raw = self.fetcher(symbols_to_fetch)
        except Exception as e:
            logger.error("TwsFeaturesProvider: Fetcher failed: %s", e, exc_info=True)
            # Return empty dicts for all requested symbols if fetch fails entirely
            return {sym: {} for sym in requested_symbols}

        # 3. Translate (The translator handles the extraction and usage of the benchmark data)
        # We pass the benchmark symbol identifier so the translator knows which data is the benchmark.
        try:
            # Pass as keyword argument for flexibility
            translated = self.translator(raw, benchmark_symbol=self.benchmark_symbol)
        except TypeError:
            # Handle cases where the translator might not yet support the new signature (backward compatibility)
            logger.warning(
                "Translator %s does not support benchmark_symbol argument. RS calculation will be inactive.",
                getattr(self.translator, "__name__", "Unknown"),
            )
            try:
                translated = self.translator(raw)
            except Exception as e:
                logger.error("TwsFeaturesProvider: Translator failed (fallback call): %s", e, exc_info=True)
                translated = {}
        except Exception as e:
            logger.error("TwsFeaturesProvider: Translator failed: %s", e, exc_info=True)
            translated = {}

        # 4. Validate structure and filter results
        # We rely on the translator to produce the correct structure (including Decimals)
        # and the core engine's Pydantic validation to ensure integrity.

        validated_output = {}
        for sym, data in translated.items():
            # We only return features for the originally requested symbols (exclude the benchmark itself)
            if sym in requested_symbols:
                if isinstance(data, dict):
                    validated_output[sym] = data
                else:
                    # Log if the translator produced invalid output
                    logger.warning(
                        "TwsFeaturesProvider: Translator produced invalid data type for symbol %s: %s. Providing empty dict.",
                        sym,
                        type(data).__name__,
                    )
                    # Provide an empty dict (Pydantic will handle defaults downstream)
                    validated_output[sym] = {}

        # Ensure all requested symbols are present in the output, even if translation failed or data was missing
        for sym in requested_symbols:
            if sym not in validated_output:
                # If a symbol was requested but not present in the translated output (e.g., fetch failed for that symbol)
                validated_output[sym] = {}

        return validated_output

    def __call__(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Backwards-compatible callable façade."""
        return self.features_for_symbols(list(symbols))
