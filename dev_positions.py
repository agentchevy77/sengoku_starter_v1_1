from optipanel.positions import PositionState, default_thresholds


# Simulate live features
def get_mock_features():
    return {
        "AAPL": {
            "last": 240.0,
            "dma20": 235.0,
            "support": 230.0,
            "resistance": 245.0,
            "rvol": 1.2,
            "rs_strength": 0.03,
            "vwap_diff": 0.01,
        },
        "MSFT": {
            "last": 508.0,
            "dma20": 505.0,
            "support": 500.0,
            "resistance": 515.0,
            "rvol": 1.1,
            "rs_strength": -0.01,
            "vwap_diff": 0.0,
        },
        "SPY": {
            "last": 660.0,
            "dma20": 650.0,
            "support": 645.0,
            "resistance": 665.0,
            "rvol": 1.0,
            "rs_strength": 0.0,
            "vwap_diff": 0.0,
        },
    }


# Run simulation
state = PositionState(cash=100000.0)
th = default_thresholds()

# More realistic thresholds
th["entry_breakout"] = 70
th["entry_trend"] = 65

for tick in range(5):
    features = get_mock_features()

    # Simulate price movement
    if tick == 2:
        features["AAPL"]["last"] = 242.0  # Small gain
    elif tick == 4:
        features["AAPL"]["last"] = 235.0  # Drop to stop loss

    result = state.tick(features, thresholds=th)
    if result["actions"]:
        print(f"Tick {tick}: {result['actions']}")
        print(f"  Equity: ${result['equity']:.2f}, Cash: ${result['cash']:.2f}")

print(f"\nFinal positions: {state.positions}")
print(f"Closed trades: {len(state.closed_trades)}")
