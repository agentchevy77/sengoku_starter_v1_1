import time

from optipanel.services.budget import BudgetMeter


def test_budget_backoff_and_cooldown():
    m = BudgetMeter(allowance=100, soft_cap=10, cooldown_sec=1)
    m.update(streams=5, snaps=3, rt_bars=1)  # total 9
    m.tick()
    assert not m.state.backoff_active
    m.update(snaps=5)  # total 11
    m.tick()
    assert m.state.backoff_active
    m.update(snaps=1)
    time.sleep(1.1)
    m.tick()
    assert not m.state.backoff_active
