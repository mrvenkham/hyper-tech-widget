"""Broker interface. Implement this to connect a real broker.

A real broker (OANDA, MetaTrader 5, a crypto exchange, ...) subclasses Broker
and implements the four methods below. Keep every method side-effect-safe:
if the API call fails, raise, and the caller will record the failure rather
than assume a fill.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Position


class Broker(ABC):
    name: str = "base"

    @abstractmethod
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
        """Open a position and return it. `side` is 'long' or 'short'."""

    @abstractmethod
    def close_position(self, position_id: str, price: float) -> float:
        """Close one position at `price`. Return realized PnL."""

    @abstractmethod
    def close_all(self, price: float) -> float:
        """Flatten everything at `price`. Return total realized PnL."""

    @abstractmethod
    def open_positions(self) -> list[Position]:
        """Return currently open positions."""
