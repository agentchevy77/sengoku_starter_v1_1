# Sengoku Project: Analogies vs. Implementation

This document serves as a bridge between the strategic trading concepts outlined in `docs/gemini/BUILD0.md` and their actual implementation within the `sengoku_starter_v1_1` codebase. It identifies which concepts are implemented, which are missing, and provides specific code locations for potential improvements.

---

## **Part 1: Stock Trading as a Roman Legion**

This section analyzes the implementation of core stock trading concepts described with a Roman Legion analogy.

### 1. High ground (Multi-timeframe uptrend + relative strength)

*   **Status:** Partially Implemented
*   **Analysis:** The system can identify a basic uptrend using a moving average, but it lacks the crucial component of relative strength.
*   **Implemented Code:**
    *   `optipanel/indicators/intra.py`: The `assemble_features_from_bars` function calculates `dma20` (a 20-period simple moving average), providing a basic trend indicator.
*   **Potential Improvement:**
    *   **Location:** `optipanel/indicators/intra.py`, within the `assemble_features_from_bars` function.
    *   **Suggestion:** Replace the hardcoded `rs_strength: 0.0` with a real calculation. This would involve fetching price data for a benchmark (e.g., SPY) and comparing the stock's performance to it over a specific period. This is a prerequisite for a true "High ground" assessment.

### 2. Reliable supply lines (Liquidity + buybacks + stable float)

*   **Status:** Implemented
*   **Analysis:** The concept of "supply lines" is well-represented through detailed volume analysis. The system rewards moves that are supported by strong participation.
*   **Implemented Code:**
    *   `optipanel/indicators/intra.py`: The `rvol_ratio` function calculates a relative volume ratio, which is a primary measure of liquidity surges.
    *   `optipanel/indicators/intra.py`: The `obv_slope` and `chaikin_ad_slope` functions confirm that volume is supporting the price trend.
    *   `optipanel/setups/engine.py`: The scoring logic for setups like `breakout_up` and `trend` explicitly gives bonuses for high relative volume (`rvol_bonus`), reinforcing this concept.
*   **Potential Improvement:**
    *   **Location:** A new adapter in `optipanel/adapters/` for fundamental data.
    *   **Suggestion:** To fully match the analogy, the system could be enhanced to pull in data on corporate buyback programs and changes in the stock's float, though the current volume analysis is a very strong proxy.

### 3. Forts captured (Resistance turned to support)

*   **Status:** Implemented
*   **Analysis:** The system identifies basic support and resistance levels, which correspond to the "forts" in the analogy.
*   **Implemented Code:**
    *   `optipanel/indicators/intra.py`: The `assemble_features_from_bars` function calculates `support` (min low of the window) and `resistance` (max high of the window).
*   **Potential Improvement:**
    *   **Location:** `optipanel/indicators/intra.py` or a new, more advanced indicator module.
    *   **Suggestion:** The current implementation is basic. This could be evolved to use more robust methods for identifying support and resistance, such as pivot points, volume profile analysis (volume-by-price), or anchored VWAPs from significant highs/lows.

### 4. Morale & standards (Positive sentiment & narrative)

*   **Status:** Implemented
*   **Analysis:** The project measures intraday buying and selling pressure, which is a direct proxy for "morale" during a trading session.
*   **Implemented Code:**
    *   `optipanel/indicators/intra.py`: The `clv` (Close Location Value) function calculates where the price closes within a bar's range. A consistently high CLV indicates strong buying pressure and high "morale."
*   **Potential Improvement:**
    *   **Location:** A new module, e.g., `optipanel/sentiment/`.
    *   **Suggestion:** To capture the "narrative" aspect, the system could be expanded to ingest and analyze news sentiment, social media mentions, or analyst ratings. This would require a new data adapter and NLP processing capabilities.

### 5. Veteran legions (Execution: beat-and-raise, margin/FCF growth)

*   **Status:** Not Implemented
*   **Analysis:** The system is completely unaware of company fundamentals. It trades based on technical data only.
*   **Potential Improvement:**
    *   **Location:** A new adapter in `optipanel/adapters/` and a new processing module like `optipanel/fundamentals/`.
    *   **Suggestion:** Implement a data adapter to pull fundamental data (e.g., from a provider like Finnhub, IEX, or a broker API). This data could then be used to create a "fundamental score" that qualifies or disqualifies technical setups, ensuring the system is only trading "veteran legions."

### 6. Intelligence & timing (Clear catalyst calendar)

*   **Status:** Not Implemented
*   **Analysis:** The system does not track any scheduled events or catalysts.
*   **Potential Improvement:**
    *   **Location:** A new module, e.g., `optipanel/events/`.
    *   **Suggestion:** Create a system to ingest an event calendar (earnings dates, FDA decisions, product launches). This could be used to increase the system's awareness or volatility expectations around specific dates, preventing it from being "ambushed."

### 7. Allied tribes (Sector leadership, ETF/index inclusion)

*   **Status:** Not Implemented
*   **Analysis:** The system operates on a single-stock basis and has no concept of its relation to a broader sector or index.
*   **Potential Improvement:**
    *   **Location:** `optipanel/indicators/` and a new adapter for sector data.
    *   **Suggestion:** This is directly tied to the `rs_strength` improvement. The system needs to be able to fetch data for sector ETFs (e.g., XLK, XLF) to compare a stock's performance against its "allied tribes." This would allow for true relative strength analysis.

### 8. Good weather (Risk-on regime)

*   **Status:** Not Implemented
*   **Analysis:** The system is unaware of the broader macro-economic environment.
*   **Potential Improvement:**
    *   **Location:** A new module, e.g., `optipanel/macro/`.
    *   **Suggestion:** Implement a mechanism to track key macro indicators like the VIX (volatility index), Treasury yields, or credit spreads. This "weather" reading could act as a global filter, making the system more or less aggressive based on overall market conditions.

---

## **Part 1.7: Advanced Tactics & Combined Arms Doctrine**

*   **Analogy:** This concept, original to our analysis, posits that the system's true strength lies not in any single indicator, but in its ability to coordinate multiple signals, much like a modern military uses "Combined Arms" (artillery, infantry, air support) for a synergistic effect. A breakout is stronger if supported by a trend, high volume, and positive market sentiment.

*   **Status:** Implemented

*   **Analysis:** The project has a sophisticated architecture for defining, scoring, and aggregating tactical signals into a cohesive final decision. This is one of the most well-developed aspects of the system.

*   **Implemented Code:**
    *   **The "Quantitative Model"** (`optipanel/setups/engine.py`): The `SetupConfig` dataclass at the top of this file defines the entire quantitative model for scoring. All scores are normalized to a **0-100 scale**.
    *   **The "Tactical Playbook"** (`optipanel/setups/engine.py`): The `compute_setups` function acts as the playbook. It does not use simple thresholds, but a more nuanced **"base score + bonus/penalty"** system. For example, the `breakout_up` score is calculated by: a) assigning a base score based on the price's proximity to resistance (e.g., 85 if already broken, 60 if near, 30 if far), and then b) adding discrete bonuses for confirming evidence, such as high relative volume (`+10`) and strong relative strength (`+10`).
    *   **The "Combined Arms" Doctrine** (`optipanel/chips/aggregate.py`): This module aggregates the various 0-100 scores from the playbook into a consolidated view, demonstrating the system's ability to synthesize multiple signals.
    *   **"Rules of Engagement"** (`optipanel/setups/engine.py`): The file defines parameters like `advice_exhaustion_veto` (70.0). This is a safety override, representing a "General's veto" that can prevent a high-scoring `breakout_up` from being acted upon if the `exhaustion` score is also dangerously high.

*   **Potential Improvement:**
    *   **Location:** `optipanel/setups/engine.py` and `optipanel/chips/aggregate.py`.
    *   **Suggestion 1 (More "Specialized Units"):** New, highly specific setups could be added to the `engine.py` playbook for nuanced market conditions, such as an "Earnings Gap Fade" or a "Low-Volatility Squeeze."
    *   **Suggestion 2 (Dynamic Weighting):** The aggregation logic in `aggregate.py` could be enhanced. Instead of static aggregation, the *weighting* of different signals could be dynamic. For example, in a high-volatility market ("bad weather"), the system could automatically give more weight to mean-reversion signals (`rejection_down`) and less to trend-following ones (`trend_long`).
    *   **Suggestion 3 (Inter-Unit Communication):** A more advanced feature would be to allow signals to directly influence each other. For example, a confirmed `breakdown_down` in a sector ETF (an "Allied Tribe" in retreat) could dramatically amplify the score of a `breakdown_down` setup for a stock within that sector. This would require the implementation of the "Allied Tribes" concept first.