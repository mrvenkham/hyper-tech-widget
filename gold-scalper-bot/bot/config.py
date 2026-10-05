"""Load configuration from config.yaml and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so we don't add a dependency. Does not override
    variables already present in the real environment."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class SessionConfig:
    enabled: bool = False
    start_utc: str = "00:00"
    end_utc: str = "23:59"
    weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])


@dataclass
class RiskConfig:
    per_trade_risk: float = 0.005
    daily_loss_limit: float = 0.03
    max_open_positions: int = 1
    require_stop_loss: bool = True
    default_stop_distance: float = 2.5


@dataclass
class AccountConfig:
    starting_balance: float = 10000.0
    currency: str = "USD"


@dataclass
class Config:
    broker: str = "paper"
    symbol: str = "XAUUSD"
    account: AccountConfig = field(default_factory=AccountConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    dashboard_refresh_seconds: int = 3

    # Secrets / runtime (from env)
    webhook_secret: str = ""
    dashboard_token: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    host: str = "0.0.0.0"
    port: int = 8000


def load_config(config_path: Path | None = None, env_path: Path | None = None) -> Config:
    config_path = config_path or (BASE_DIR / "config.yaml")
    env_path = env_path or (BASE_DIR / ".env")
    _load_dotenv(env_path)

    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text()) or {}

    cfg = Config(
        broker=raw.get("broker", "paper"),
        symbol=raw.get("symbol", "XAUUSD"),
        account=AccountConfig(**(raw.get("account") or {})),
        risk=RiskConfig(**(raw.get("risk") or {})),
        session=SessionConfig(**(raw.get("session") or {})),
        dashboard_refresh_seconds=int(raw.get("dashboard_refresh_seconds", 3)),
        webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
        dashboard_token=os.environ.get("DASHBOARD_TOKEN", ""),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
    return cfg
