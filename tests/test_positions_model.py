from optipanel.positions.model import Position, PositionState, default_thresholds


def _thresholds():
    th = default_thresholds()
    th["risk_per_trade"] = 0.02
    return th


def test_tick_enters_position_when_thresholds_hit(mocker):
    state = PositionState(cash=10_000.0)
    mocker.patch(
        "optipanel.positions.model.compute_setups",
        return_value={
            "breakout_up": 90,
            "trend_long": 85,
        },
    )
    features = {"AAPL": {"last": 100.0}}

    result = state.tick(features, thresholds=_thresholds())

    assert result["actions"] == ["BUY AAPL x2 @ 100.00"]
    assert state.positions["AAPL"].qty == 2
    assert state.cash == 10_000.0 - (2 * 100.0)


def test_tick_exits_and_starts_cooldown(mocker):
    state = PositionState(cash=0.0)
    state.positions["AAPL"] = Position("AAPL", qty=10, avg_px=100.0)
    th = _thresholds()
    mocker.patch(
        "optipanel.positions.model.compute_setups",
        return_value={
            "breakdown_down": 90,
            "trend_long": 90,
            "breakout_up": 90,
        },
    )
    features = {"AAPL": {"last": 90.0}}

    result = state.tick(features, thresholds=th)

    assert result["actions"] == ["EXIT AAPL x10 @ 90.00 pnl=-100.00"]
    assert "AAPL" not in state.positions
    assert state.cash == 900.0
    assert state.cooldown["AAPL"] == th["cooldown_ticks"]
    assert not any(action.startswith("BUY") for action in result["actions"])
