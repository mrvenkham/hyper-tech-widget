"""Paper (simulated) broker. The default. Places no real orders.

PnL model is deliberately simple: 1 unit of qty = 1 unit of price movement in
account currency. For XAUUSD that means qty is "dollars of gold per $1 move",
which keeps the risk math in risk.py consistent (risk_amount / stop_distance).

-------------------------------------------------------------------------------
Implementing a REAL broker instead
-------------------------------------------------------------------------------
Subclass bot.brokers.base.Broker and register it in bot/brokers/__init__.py.

* OANDA (REST, no Windows needed, good for spot-gold CFDs):
    Use the v20 REST API. open_position -> POST /v3/accounts/{id}/orders with a
    MARKET order plus stopLossOnFill / takeProfitOnFill. Map qty to "units".
* MetaTrader 5 (Windows only, Python package `MetaTrader5`):
    mt5.initialize(); mt5.order_send(request) with action=TRADE_ACTION_DEAL.
    Run on a Windows VPS. The phone's MT5 app can monitor but not run this.
* Crypto exchange (PAXG/XAUT, 24/7, runs anywhere) via `ccxt`:
    exchange.create_order(symbol, 'market', side, amount, params={...}).

In every case, convert the real fill price and size back into Position so the
dashboard and risk logic keep working unchanged.
"""

from __future__ import annotations

import time
import uuid

from ..config import Config
from ..models import Position
from ..state import BotState
from .base import Broker


class PaperBroker(Broker):
    name = "paper"

    def __init__(self, cfg: Config, state: BotState):
        self.cfg = cfg
        self.state = state
        self._positions: dict[str, Position] = {}

    def open_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        sl: float | None = None,
        tp: float | None = None,
        comment: str = "",
    ) -> Position:
        pos = Position(
            id=uuid.uuid4().hex[:12],
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=price,
            sl=sl,
            tp=tp,
            opened_at=time.time(),
        )
        self._positions[pos.id] = pos
        self.state.set_event(f"opened {side} {qty} {symbol} @ {price}")
        return pos

    def _pnl(self, pos: Position, exit_price: float) -> float:
        direction = 1.0 if pos.side == "long" else -1.0
        return round(direction * (exit_price - pos.entry_price) * pos.qty, 2)

    def close_position(self, position_id: str, price: float) -> float:
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return 0.0
        pnl = self._pnl(pos, price)
        self.state.record_trade(
            {
                "id": pos.id,
                "symbol": pos.symbol,
                "side": pos.side,
                "qty": pos.qty,
                "entry_price": pos.entry_price,
                "exit_price": price,
                "pnl": pnl,
                "opened_at": pos.opened_at,
                "closed_at": time.time(),
                "comment": "",
            }
        )
        return pnl

    def close_all(self, price: float) -> float:
        total = 0.0
        for pid in list(self._positions.keys()):
            total += self.close_position(pid, price)
        return round(total, 2)

    def open_positions(self) -> list[Position]:
        return list(self._positions.values())
