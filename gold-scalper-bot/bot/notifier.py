"""Optional Telegram alerts. Silently no-ops if not configured."""

from __future__ import annotations

import logging

import httpx

from .config import Config

log = logging.getLogger("notifier")


class Notifier:
    def __init__(self, cfg: Config):
        self.token = cfg.telegram_bot_token
        self.chat_id = cfg.telegram_chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"chat_id": self.chat_id, "text": text})
        except httpx.HTTPError as exc:  # never let an alert failure break trading
            log.warning("Telegram alert failed: %s", exc)
