import time

from optipanel.services import budget as budget_mod
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


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def time(self) -> float:
        return self.now


def test_budget_cooldown_requires_full_interval(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(budget_mod.time, "time", fake.time)

    meter = BudgetMeter(allowance=100, soft_cap=10, cooldown_sec=2)
    meter.update(streams=6, snaps=2, rt_bars=0)  # total 8 -> below cap
    meter.tick()
    assert not meter.state.backoff_active

    fake.advance(0.1)
    meter.update(rt_bars=5)  # total 13 -> breach
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(0.2)
    meter.update(rt_bars=1)  # total 9 -> below cap but cooldown just started
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(1.0)
    meter.tick()
    assert meter.state.backoff_active  # cooldown not yet satisfied

    fake.advance(1.1)
    meter.tick()
    assert not meter.state.backoff_active


def test_budget_fluctuations_reset_cooldown(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(budget_mod.time, "time", fake.time)

    meter = BudgetMeter(allowance=100, soft_cap=10, cooldown_sec=3)
    meter.update(streams=6, snaps=5, rt_bars=1)  # 12 -> breach
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(1.0)
    meter.update(snaps=2, rt_bars=0)  # 8 -> drop below cap, start cooldown window
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(1.4)
    meter.tick()
    assert meter.state.backoff_active  # still within original cooldown

    fake.advance(0.2)
    meter.update(snaps=5, rt_bars=1)  # 12 -> breach again, cooldown should restart
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(3.1)
    meter.tick()
    assert meter.state.backoff_active  # still above cap until usage drops
    meter.update(snaps=2, rt_bars=0)
    meter.tick()
    assert meter.state.backoff_active

    fake.advance(3.1)
    meter.tick()
    assert not meter.state.backoff_active
