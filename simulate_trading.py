import argparse
import random

from optipanel.positions import PositionState, default_thresholds


def simulate_price_movement(features, tick):
    """Simulate realistic price movements"""
    for sym in features:
        last = features[sym]["last"]
        # Random walk with slight upward bias
        change = random.uniform(-0.02, 0.025) if tick < 10 else random.uniform(-0.03, 0.02)
        features[sym]["last"] = round(last * (1 + change), 2)
    return features


# Initial features
features = {
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


def main():
    parser = argparse.ArgumentParser(description="Trading simulation with performance profiling")
    parser.add_argument("--ticks", type=int, default=20, help="Number of ticks to simulate")
    args = parser.parse_args()

    # Initialize features
    features = {
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

    state = PositionState(cash=100000.0)
    th = default_thresholds()
    th["entry_breakout"] = 70
    th["entry_trend"] = 65

    print(f"Starting simulation with $100,000 for {args.ticks} ticks")
    for tick in range(args.ticks):
        features = simulate_price_movement(features, tick)
        result = state.tick(features, thresholds=th)

        if result["actions"]:
            for action in result["actions"]:
                print(f"Tick {tick:2d}: {action}")
            print(f"         Equity: ${result['equity']:.2f}, Positions: {len(result['positions'])}")

    print("\nFinal Summary:")
    print(f"  Ending equity: ${result['equity']:.2f}")
    print(f"  Open positions: {len(state.positions)}")
    print(f"  Closed trades: {len(state.closed_trades)}")
    if state.closed_trades:
        total_pnl = sum(t.pnl for t in state.closed_trades)
        print(f"  Total P&L: ${total_pnl:.2f}")


if __name__ == "__main__":
    main()
