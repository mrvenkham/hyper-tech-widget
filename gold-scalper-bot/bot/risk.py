"""Risk management: decides whether a signal may be acted on and sizes it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dtime, timezone

from .config import Config
from .models import Action, Signal
from .state import BotState


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    qty: float = 0.0
    sl: float | None = None
    tp: float | None = None


def _parse_hhmm(value: str) -> dtime:
    hh, mm = value.split(":")
    return dtime(int(hh), int(mm))


def _within_session(cfg: Config, now: datetime | None = None) -> bool:
    s = cfg.session
    if not s.enabled:
        return True
    now = now or datetime.now(timezone.utc)
    if now.weekday() not in s.weekdays:
        return False
    start = _parse_hhmm(s.start_utc)
    end = _parse_hhmm(s.end_utc)
    t = now.timetz().replace(tzinfo=None)
    if start <= end:
        return start <= t <= end
    # Window wraps past midnight.
    return t >= start or t <= end


class RiskManager:
    def __init__(self, cfg: Config, state: BotState):
        self.cfg = cfg
        self.state = state

    def daily_loss_breached(self) -> bool:
        self.state.roll_day_if_needed()
        limit = self.cfg.risk.daily_loss_limit * self.state.day_start_balance
        return self.state.realized_pnl_today <= -abs(limit)

    def evaluate(self, signal: Signal, open_positions: int, now: datetime | None = None) -> RiskDecision:
        """Entry signals (buy/sell) are checked against every rule and sized.
        Exit signals (close/flat) always pass so you can always get out."""
        if signal.action in (Action.CLOSE, Action.FLAT):
            return RiskDecision(True, "exit always permitted")

        if not self.state.trading_enabled:
            return RiskDecision(False, "trading halted (kill switch)")

        if not _within_session(self.cfg, now):
            return RiskDecision(False, "outside trading session")

        if self.daily_loss_breached():
            return RiskDecision(False, "daily loss limit reached")

        if open_positions >= self.cfg.risk.max_open_positions:
            return RiskDecision(False, "max open positions reached")

        if signal.price is None or signal.price <= 0:
            return RiskDecision(False, "signal missing a valid price")

        sl = signal.sl
        if sl is None:
            if self.cfg.risk.require_stop_loss:
                return RiskDecision(False, "signal missing stop-loss")
            # Derive a stop from the configured default distance.
            dist = self.cfg.risk.default_stop_distance
            sl = signal.price - dist if signal.action == Action.BUY else signal.price + dist

        stop_distance = abs(signal.price - sl)
        if stop_distance <= 0:
            return RiskDecision(False, "stop-loss equals entry price")

        risk_amount = self.cfg.risk.per_trade_risk * self.state.balance
        qty = risk_amount / stop_distance
        qty = round(qty, 4)
        if qty <= 0:
            return RiskDecision(False, "computed size is zero")

        return RiskDecision(True, "ok", qty=qty, sl=sl, tp=signal.tp)
