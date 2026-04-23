"""LINE Messaging API notifier.

Parallel channel to Telegram. LINE is used for *raw alerts* to multiple
subscribers filtered by category (CRC / SDS); Telegram carries the
LLM-processed curated digest for a single operator.

Design note
-----------
LINE's push API requires a recipient ID on every call, unlike Telegram
where the chat_id is fixed at bot level. To keep the BaseNotifier
interface (``send(message) -> bool``) uniform, we bind ``user_id`` in
the constructor and create one instance per subscriber. It's cheap —
no network at construction — and keeps the call-site symmetric with
TelegramNotifier.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from notifier.base_notifier import BaseNotifier

logger = logging.getLogger("journal_tracker")


class LineNotifier(BaseNotifier):
    """Send a single push message to one LINE user."""

    MAX_LENGTH = 5000  # LINE push limit per message
    API_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(self, channel_access_token: str, user_id: str) -> None:
        self._token = channel_access_token
        self._user_id = user_id
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {channel_access_token}",
        }

    def send(self, message: str) -> bool:
        """Send a single message. Long messages are truncated at MAX_LENGTH."""
        if len(message) > self.MAX_LENGTH:
            logger.warning(
                f"LINE message exceeds {self.MAX_LENGTH} chars; truncating "
                f"({len(message)} -> {self.MAX_LENGTH})"
            )
            message = message[: self.MAX_LENGTH - 3] + "..."

        return self._push(message)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((requests.RequestException,)),
    )
    def _push(self, text: str) -> bool:
        payload: dict[str, Any] = {
            "to": self._user_id,
            "messages": [{"type": "text", "text": text}],
        }
        try:
            response = requests.post(
                self.API_URL, json=payload, headers=self._headers, timeout=15
            )
            if response.status_code == 200:
                return True
            logger.error(
                f"LINE send failed ({response.status_code}) "
                f"for user {self._user_id[:8]}...: {response.text[:300]}"
            )
            return False
        except requests.RequestException as e:
            logger.error(f"LINE request exception: {e}")
            raise
