"""Broker implementations. Select one via `broker:` in config.yaml."""

from __future__ import annotations

from ..config import Config
from ..state import BotState
from .base import Broker
from .paper import PaperBroker


def make_broker(cfg: Config, state: BotState) -> Broker:
    name = (cfg.broker or "paper").lower()
    if name == "paper":
        return PaperBroker(cfg, state)
    raise ValueError(
        f"Unknown broker '{cfg.broker}'. Only 'paper' ships by default. "
        "Add your own in bot/brokers/ and register it here."
    )
