from __future__ import annotations

import logging

import requests

from trader.config import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.telegram_enabled and bool(settings.telegram_bot_token and settings.telegram_chat_id)
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.timeout = settings.telegram_timeout_seconds

    def send(self, message: str) -> None:
        if not self.enabled:
            return
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Telegram notification failed: %s", exc)
