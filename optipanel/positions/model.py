from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from optipanel.setups.engine import compute_setups


def _coerce_price(value: Any) -> float | None:
    """Return a finite positive price or ``None`` when input is unusable."""

    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0.0:
        return None
    return price


def default_thresholds() -> dict[str, float]:
    return {
        "entry_breakout": 80,  # breakout_up >= 80
        "entry_trend": 70,  # trend_long >= 70
        "exit_breakdown": 80,  # breakdown_down >= 80
        "exit_trend": 70,  # trend_short >= 70
        "stop_loss": -0.05,  # -5%
        "take_profit": 0.10,  # +10%
        "cooldown_ticks": 2,
        "risk_per_trade": 0.02,  # 2% of cash
    }


@dataclass
class Trade:
    symbol: str
    side: str  # 'long'
    qty: int
    entry_px: float
    exit_px: float | None = None
    pnl: float | None = None


@dataclass
class Position:
    symbol: str
    qty: int
    avg_px: float


@dataclass
class PositionState:
    cash: float = 100_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    open_trades: list[Trade] = field(default_factory=list)
    closed_trades: list[Trade] = field(default_factory=list)
    cooldown: dict[str, int] = field(default_factory=dict)
    tick_index: int = 0

    def _dec_cooldowns(self) -> None:
        to_clear = []
        for s, v in self.cooldown.items():
            nv = max(0, v - 1)
            self.cooldown[s] = nv
            if nv == 0:
                to_clear.append(s)
        for s in to_clear:
            self.cooldown.pop(s, None)

    def _should_exit(self, sym: str, last: float, setups: dict[str, int], th: dict[str, float]) -> bool:
        pos = self.positions.get(sym)
        if not pos:
            return False
        # threshold exits
        if setups.get("breakdown_down", 0) >= th["exit_breakdown"]:
            return True
        if setups.get("trend_short", 0) >= th["exit_trend"]:
            return True
        # stop / take
        change = (last / pos.avg_px) - 1.0 if pos.avg_px else 0.0
        if change <= th["stop_loss"]:
            return True
        return change >= th["take_profit"]

    def _should_enter_long(self, sym: str, setups: dict[str, int], th: dict[str, float]) -> bool:
        if sym in self.positions:
            return False
        if self.cooldown.get(sym, 0) > 0:
            return False
        return setups.get("breakout_up", 0) >= th["entry_breakout"] and setups.get("trend_long", 0) >= th["entry_trend"]

    def tick(
        self,
        features: dict[str, dict[str, Any]],
        thresholds: dict[str, float] | None = None,
        symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        One discrete step: evaluate setups, generate entries/exits, update cash and positions.
        """
        th = thresholds or default_thresholds()
        self.tick_index += 1
        self._dec_cooldowns()

        syms = list(symbols or features.keys())
        actions: list[str] = []
        setup_cache: dict[str, dict[str, int]] = {}

        def _get_setups(sym: str, feat: dict[str, Any]) -> dict[str, int]:
            cached = setup_cache.get(sym)
            if cached is not None:
                return cached
            setups = compute_setups(feat)
            setup_cache[sym] = setups
            return setups

        # exits first (respect risk)
        for sym in list(syms):
            pos = self.positions.get(sym)
            if not pos:
                continue
            f = features.get(sym) or {}
            last = _coerce_price(f.get("last"))
            if last is None:
                continue
            setups = _get_setups(sym, f)
            if self._should_exit(sym, last, setups, th):
                pnl = (last - pos.avg_px) * pos.qty
                self.cash += pos.qty * last
                self.closed_trades.append(Trade(sym, "long", pos.qty, pos.avg_px, last, pnl))
                actions.append(f"EXIT {sym} x{pos.qty} @ {last:.2f} pnl={pnl:.2f}")
                del self.positions[sym]
                self.cooldown[sym] = int(th["cooldown_ticks"])

        # entries
        for sym in syms:
            if sym in self.positions:
                continue
            f = features.get(sym) or {}
            last = _coerce_price(f.get("last"))
            if last is None:
                continue
            setups = _get_setups(sym, f)
            if self._should_enter_long(sym, setups, th):
                risk_cap = self.cash * float(th.get("risk_per_trade", 0.02))
                qty = max(0, int(risk_cap / last))
                if qty <= 0:
                    continue
                cost = qty * last
                if cost > self.cash:
                    qty = int(self.cash // last)
                    cost = qty * last
                if qty <= 0:
                    continue
                self.cash -= cost
                self.positions[sym] = Position(sym, qty, last)
                self.open_trades.append(Trade(sym, "long", qty, last))
                actions.append(f"BUY {sym} x{qty} @ {last:.2f}")

        equity = self.cash
        for sym, pos in self.positions.items():
            last = _coerce_price(features.get(sym, {}).get("last"))
            if last is None:
                continue
            equity += pos.qty * last
        return {
            "i": self.tick_index,
            "cash": round(self.cash, 2),
            "equity": round(equity, 2),
            "positions": {s: {"qty": p.qty, "avg_px": p.avg_px} for s, p in self.positions.items()},
            "actions": actions,
        }
