from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from optipanel.setups.engine import compute_setups
from optipanel.utils.decimal_types import (
    D_ZERO,
    to_decimal,
    to_float,
)


def _coerce_price(value: Any) -> Decimal | None:
    """Return a finite positive price as Decimal or ``None`` when input is unusable.

    Uses Decimal for precise financial calculations.
    """
    price = to_decimal(value, default=None)  # type: ignore
    if price is None:
        return None
    if not price.is_finite() or price <= D_ZERO:
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
    entry_px: Decimal  # Precise price tracking with Decimal
    exit_px: Decimal | None = None
    pnl: Decimal | None = None  # Precise P&L tracking

    def __post_init__(self):
        """Ensure prices are always Decimal for backward compatibility."""
        if not isinstance(self.entry_px, Decimal):
            self.entry_px = to_decimal(self.entry_px, default=D_ZERO)
        if self.exit_px is not None and not isinstance(self.exit_px, Decimal):
            self.exit_px = to_decimal(self.exit_px, default=D_ZERO)
        if self.pnl is not None and not isinstance(self.pnl, Decimal):
            self.pnl = to_decimal(self.pnl, default=D_ZERO)


@dataclass
class Position:
    symbol: str
    qty: int
    avg_px: Decimal  # Precise average price tracking

    def __post_init__(self):
        """Ensure avg_px is always Decimal for backward compatibility."""
        if not isinstance(self.avg_px, Decimal):
            self.avg_px = to_decimal(self.avg_px, default=D_ZERO)


@dataclass
class PositionState:
    cash: Decimal = Decimal("100000.00")  # Precise cash tracking with Decimal
    positions: dict[str, Position] = field(default_factory=dict)
    open_trades: list[Trade] = field(default_factory=list)
    closed_trades: list[Trade] = field(default_factory=list)
    cooldown: dict[str, int] = field(default_factory=dict)
    tick_index: int = 0

    def __post_init__(self):
        """Ensure cash is always Decimal for backward compatibility."""
        if not isinstance(self.cash, Decimal):
            self.cash = to_decimal(self.cash, default=Decimal("100000.00"))

    def _dec_cooldowns(self) -> None:
        to_clear = []
        for s, v in self.cooldown.items():
            nv = max(0, v - 1)
            self.cooldown[s] = nv
            if nv == 0:
                to_clear.append(s)
        for s in to_clear:
            self.cooldown.pop(s, None)

    def _should_exit(self, sym: str, last: Decimal, setups: dict[str, int], th: dict[str, float]) -> bool:
        """Check exit conditions with precise Decimal calculations."""
        pos = self.positions.get(sym)
        if not pos:
            return False
        # threshold exits
        if setups.get("breakdown_down", 0) >= th["exit_breakdown"]:
            return True
        if setups.get("trend_short", 0) >= th["exit_trend"]:
            return True
        # stop / take - using Decimal for precise percentage calculations
        if abs(pos.avg_px) < Decimal("1e-9"):
            change = D_ZERO
        else:
            change = (last / pos.avg_px) - Decimal("1")

        stop_loss_d = Decimal(str(th["stop_loss"]))
        take_profit_d = Decimal(str(th["take_profit"]))

        if change <= stop_loss_d:
            return True
        return change >= take_profit_d

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

        Uses Decimal arithmetic for precise P&L and cash calculations to avoid floating-point errors.
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

        # exits first (respect risk) - using Decimal for precise P&L
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
                # Precise P&L calculation with Decimal
                pnl = (last - pos.avg_px) * Decimal(str(pos.qty))
                self.cash += Decimal(str(pos.qty)) * last
                self.closed_trades.append(Trade(sym, "long", pos.qty, pos.avg_px, last, pnl))
                # Convert to float for display
                actions.append(f"EXIT {sym} x{pos.qty} @ {to_float(last):.2f} pnl={to_float(pnl):.2f}")
                del self.positions[sym]
                self.cooldown[sym] = int(th["cooldown_ticks"])

        # entries - using Decimal for precise cost calculations
        for sym in syms:
            if sym in self.positions:
                continue
            f = features.get(sym) or {}
            last = _coerce_price(f.get("last"))
            if last is None:
                continue
            setups = _get_setups(sym, f)
            if self._should_enter_long(sym, setups, th):
                risk_cap = self.cash * Decimal(str(th.get("risk_per_trade", 0.02)))
                qty = max(0, int(risk_cap / last))
                if qty <= 0:
                    continue
                cost = Decimal(str(qty)) * last
                if cost > self.cash:
                    qty = int(self.cash // last)
                    cost = Decimal(str(qty)) * last
                if qty <= 0:
                    continue
                self.cash -= cost
                self.positions[sym] = Position(sym, qty, last)
                self.open_trades.append(Trade(sym, "long", qty, last))
                # Convert to float for display
                actions.append(f"BUY {sym} x{qty} @ {to_float(last):.2f}")

        # Calculate equity with precise Decimal arithmetic
        equity = self.cash
        for sym, pos in self.positions.items():
            last = _coerce_price(features.get(sym, {}).get("last"))
            if last is None:
                continue
            equity += Decimal(str(pos.qty)) * last

        return {
            "i": self.tick_index,
            "cash": round(to_float(self.cash), 2),
            "equity": round(to_float(equity), 2),
            "positions": {s: {"qty": p.qty, "avg_px": to_float(p.avg_px)} for s, p in self.positions.items()},
            "actions": actions,
        }
