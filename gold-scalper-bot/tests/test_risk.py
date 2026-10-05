"""Risk manager tests. No network, no real broker."""

from __future__ import annotations

import tempfile
from pathlib import Path

from bot.config import AccountConfig, Config, RiskConfig, SessionConfig
from bot.models import Action, Signal
from bot.risk import RiskManager
from bot.state import BotState


def make_state(balance=10000.0):
    tmp = Path(tempfile.mkdtemp()) / "state.json"
    return BotState(balance, path=tmp)


def base_cfg(**risk_kwargs):
    return Config(
        broker="paper",
        symbol="XAUUSD",
        account=AccountConfig(starting_balance=10000.0),
        risk=RiskConfig(**risk_kwargs),
        session=SessionConfig(enabled=False),
    )


def buy(price=2000.0, sl=1995.0, tp=2010.0):
    return Signal(secret="x", action=Action.BUY, symbol="XAUUSD", price=price, sl=sl, tp=tp)


def test_position_sizing_matches_risk_budget():
    cfg = base_cfg(per_trade_risk=0.01)  # risk 1% = $100
    state = make_state(10000.0)
    rm = RiskManager(cfg, state)
    d = rm.evaluate(buy(price=2000.0, sl=1995.0), open_positions=0)
    assert d.allowed
    # stop distance = 5, budget = 100 -> qty = 20
    assert d.qty == 20.0


def test_rejects_when_stop_missing_and_required():
    cfg = base_cfg(require_stop_loss=True)
    rm = RiskManager(cfg, make_state())
    sig = Signal(secret="x", action=Action.BUY, symbol="XAUUSD", price=2000.0, sl=None)
    d = rm.evaluate(sig, open_positions=0)
    assert not d.allowed and "stop-loss" in d.reason


def test_derives_stop_when_not_required():
    cfg = base_cfg(require_stop_loss=False, default_stop_distance=2.5, per_trade_risk=0.01)
    rm = RiskManager(cfg, make_state(10000.0))
    sig = Signal(secret="x", action=Action.BUY, symbol="XAUUSD", price=2000.0, sl=None)
    d = rm.evaluate(sig, open_positions=0)
    assert d.allowed
    assert d.sl == 1997.5
    assert d.qty == 40.0  # budget 100 / distance 2.5


def test_max_open_positions_blocks():
    cfg = base_cfg(max_open_positions=1)
    rm = RiskManager(cfg, make_state())
    d = rm.evaluate(buy(), open_positions=1)
    assert not d.allowed and "max open" in d.reason


def test_kill_switch_blocks_entries_but_allows_exit():
    cfg = base_cfg()
    state = make_state()
    state.set_trading_enabled(False, "test")
    rm = RiskManager(cfg, state)
    assert not rm.evaluate(buy(), 0).allowed
    exit_sig = Signal(secret="x", action=Action.CLOSE, symbol="XAUUSD", price=2000.0)
    assert rm.evaluate(exit_sig, 0).allowed


def test_daily_loss_limit_blocks_new_entries():
    cfg = base_cfg(daily_loss_limit=0.03)  # $300 on 10k
    state = make_state(10000.0)
    state.record_trade({"id": "a", "symbol": "XAUUSD", "side": "long", "qty": 1,
                        "entry_price": 1, "exit_price": 0, "pnl": -350.0,
                        "opened_at": 0, "closed_at": 0})
    rm = RiskManager(cfg, state)
    assert rm.daily_loss_breached()
    assert not rm.evaluate(buy(), 0).allowed
