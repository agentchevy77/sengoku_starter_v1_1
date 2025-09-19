import time

import click

from optipanel.adapters.ibkr import RealTwsFetcher, cfg_from_env
from optipanel.positions import PositionState, default_thresholds


@click.command()
@click.option("--capital", default=100000.0, help="Starting capital")
@click.option("--risk", default=0.02, help="Risk per trade (0.02 = 2%)")
@click.option("--symbols", default="AAPL,MSFT,SPY", help="Comma-separated symbols")
@click.option("--ticks", default=1, help="Number of ticks to run")
@click.option("--interval", default=60, help="Seconds between ticks")
def live_positions(capital, risk, symbols, ticks, interval):
    """Run live position tracking with TWS data."""
    symbol_list = symbols.split(",")

    # Initialize
    fetcher = RealTwsFetcher(cfg_from_env())
    state = PositionState(cash=capital)
    th = default_thresholds()
    th["risk_per_trade"] = risk

    for tick_num in range(ticks):
        # Fetch live data
        features = fetcher.features_for_symbols(symbol_list)

        # Run position logic
        result = state.tick(features, thresholds=th)

        # Output
        print(f"\n--- Tick {tick_num + 1} ---")
        for sym, feat in features.items():
            print(f"{sym}: ${feat['last']:.2f}")

        if result["actions"]:
            for action in result["actions"]:
                print(f"  ACTION: {action}")

        print(f"Equity: ${result['equity']:.2f}, Cash: ${result['cash']:.2f}")
        print(f"Positions: {len(result['positions'])}")

        if tick_num < ticks - 1:
            time.sleep(interval)

    # Final summary
    print("\n=== FINAL ===")
    print(f"Equity: ${result['equity']:.2f}")
    print(f"Open positions: {state.positions}")
    if state.closed_trades:
        total_pnl = sum(t.pnl for t in state.closed_trades if t.pnl)
        print(f"Closed trades: {len(state.closed_trades)}, Total P&L: ${total_pnl:.2f}")


if __name__ == "__main__":
    live_positions()
