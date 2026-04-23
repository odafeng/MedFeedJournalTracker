"""Notifier service — formats a digest of new articles and pushes via Telegram."""

from __future__ import annotations

import logging
from typing import Any

from database.supabase_client import SupabaseClient
from notifier.base_notifier import BaseNotifier
from notifier.formatter import format_digest

logger = logging.getLogger("journal_tracker")


class NotifierService:
    """Build digest and send to configured notifier."""

    def __init__(self, db: SupabaseClient, notifier: BaseNotifier) -> None:
        self.db = db
        self.notifier = notifier

    def run(self, articles: list[dict[str, Any]]) -> bool:
        """Send a digest of the given articles. Returns True on success.

        `articles` should be newly-inserted articles with LLM fields populated.
        If LLM fields are missing (LLM disabled / failed), articles still
        render in a degraded mode.
        """
        if not articles:
            logger.info("No new articles to notify about")
            message = format_digest([], title="📚 Journal Feed")
            return self.notifier.send(message)

        # Enrich articles with journal_name if not already present (defensive)
        for a in articles:
            if "journal_name" not in a:
                a["journal_name"] = "Unknown"

        message = format_digest(articles, title="📚 Journal Feed")
        logger.info(f"Sending digest of {len(articles)} articles ({len(message)} chars)")

        success = self.notifier.send(message)

        # Log per-article notification status for articles that had IDs
        for a in articles:
            if a.get("id"):
                self.db.log_notification(
                    article_id=a["id"],
                    subscriber_id=None,
                    status="success" if success else "failed",
                )

        return success
