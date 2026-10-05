"""Data models for signals, positions, and trades."""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    FLAT = "flat"


class Signal(BaseModel):
    """Payload sent by TradingView alerts."""

    secret: str = ""
    action: Action
    symbol: str
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    strategy: str = "gold_scalper"
    comment: str = ""


class Position(BaseModel):
    id: str
    symbol: str
    side: str  # "long" or "short"
    qty: float
    entry_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    opened_at: float = Field(default_factory=time.time)


class Trade(BaseModel):
    id: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: float
    pnl: float
    opened_at: float
    closed_at: float = Field(default_factory=time.time)
    comment: str = ""
