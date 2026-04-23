"""Telegram Bot API notifier.

Replaces LINE Messaging API as the primary push channel (no monthly quota).
- Uses HTML parse_mode for bold/links.
- Splits long messages at 4000 chars (Telegram limit is 4096).
- Retries on transient errors with exponential backoff.
"""

from __future__ import annotations

import logging
import time
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


class TelegramNotifier(BaseNotifier):
    """Send messages via Telegram Bot API."""

    MAX_LENGTH = 4000  # Telegram hard limit is 4096; leave margin for part markers
    API_BASE = "https://api.telegram.org"

    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"{self.API_BASE}/bot{token}/sendMessage"

    def send(self, message: str) -> bool:
        if len(message) <= self.MAX_LENGTH:
            return self._send_part(message)

        parts = self._split(message)
        logger.info(f"Message split into {len(parts)} parts")
        all_ok = True
        for idx, part in enumerate(parts, 1):
            prefix = f"[{idx}/{len(parts)}]\n\n" if len(parts) > 1 else ""
            ok = self._send_part(prefix + part)
            all_ok = all_ok and ok
            # Small delay between parts to be polite
            if idx < len(parts):
                time.sleep(0.3)
        return all_ok

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((requests.RequestException,)),
    )
    def _send_part(self, text: str) -> bool:
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=15)
            if response.status_code == 200:
                return True
            logger.error(f"Telegram send failed ({response.status_code}): {response.text[:300]}")
            return False
        except requests.RequestException as e:
            logger.error(f"Telegram request exception: {e}")
            raise

    def _split(self, message: str) -> list[str]:
        """Split at paragraph boundaries, fall back to line boundaries."""
        parts: list[str] = []
        current = ""
        for para in message.split("\n\n"):
            if len(para) > self.MAX_LENGTH:
                # Single paragraph too long — split by lines
                if current:
                    parts.append(current.strip())
                    current = ""
                for line in para.split("\n"):
                    if len(current) + len(line) + 1 <= self.MAX_LENGTH:
                        current += line + "\n"
                    else:
                        parts.append(current.strip())
                        current = line + "\n"
            elif len(current) + len(para) + 2 <= self.MAX_LENGTH:
                current += para + "\n\n"
            else:
                parts.append(current.strip())
                current = para + "\n\n"
        if current.strip():
            parts.append(current.strip())
        return parts
