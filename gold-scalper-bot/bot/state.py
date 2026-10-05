"""Persisted bot state: balance, day tracking, kill switch, trade log."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "state.json"


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BotState:
    """Thread-safe state container, persisted to a JSON file."""

    def __init__(self, starting_balance: float, path: Path | None = None):
        self._lock = threading.RLock()
        self._path = path or STATE_PATH
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.trading_enabled = True          # false = halted by kill switch
        self.day = _today_utc()
        self.day_start_balance = starting_balance
        self.realized_pnl_today = 0.0
        self.trades: list[dict[str, Any]] = []
        self.last_event: str = "initialized"
        self.last_event_at: float = time.time()
        self._load()

    # --- persistence ---
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        self.balance = data.get("balance", self.balance)
        self.trading_enabled = data.get("trading_enabled", True)
        self.day = data.get("day", self.day)
        self.day_start_balance = data.get("day_start_balance", self.balance)
        self.realized_pnl_today = data.get("realized_pnl_today", 0.0)
        self.trades = data.get("trades", [])
        self.last_event = data.get("last_event", "loaded")
        self.last_event_at = data.get("last_event_at", time.time())

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2))
        tmp.replace(self._path)

    # --- day rollover ---
    def roll_day_if_needed(self) -> None:
        with self._lock:
            today = _today_utc()
            if today != self.day:
                self.day = today
                self.day_start_balance = self.balance
                self.realized_pnl_today = 0.0
                self._save()

    # --- mutations ---
    def record_trade(self, trade: dict[str, Any]) -> None:
        with self._lock:
            self.roll_day_if_needed()
            self.balance += trade["pnl"]
            self.realized_pnl_today += trade["pnl"]
            self.trades.append(trade)
            self.trades = self.trades[-500:]  # cap log size
            self.set_event(f"trade closed pnl={trade['pnl']:.2f}")

    def set_trading_enabled(self, enabled: bool, reason: str = "") -> None:
        with self._lock:
            self.trading_enabled = enabled
            self.set_event(("armed" if enabled else "halted") + (f": {reason}" if reason else ""))

    def set_event(self, msg: str) -> None:
        self.last_event = msg
        self.last_event_at = time.time()
        self._save()

    # --- views ---
    def to_dict(self) -> dict[str, Any]:
        return {
            "starting_balance": self.starting_balance,
            "balance": round(self.balance, 2),
            "trading_enabled": self.trading_enabled,
            "day": self.day,
            "day_start_balance": round(self.day_start_balance, 2),
            "realized_pnl_today": round(self.realized_pnl_today, 2),
            "trades": self.trades,
            "last_event": self.last_event,
            "last_event_at": self.last_event_at,
        }
