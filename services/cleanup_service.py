"""Cleanup service — keeps the DB bounded via RPC functions."""

from __future__ import annotations

import logging

from database.supabase_client import SupabaseClient

logger = logging.getLogger("journal_tracker")


class CleanupService:
    """Retention management for articles and notifications tables."""

    def __init__(
        self,
        db: SupabaseClient,
        max_articles: int = 10000,
        max_notifications: int = 500,
    ) -> None:
        self.db = db
        self.max_articles = max_articles
        self.max_notifications = max_notifications

    def run(self) -> dict[str, int]:
        logger.info("Running cleanup...")
        articles_deleted = self.db.cleanup_articles(self.max_articles)
        notifications_deleted = self.db.cleanup_notifications(self.max_notifications)
        return {
            "articles_deleted": articles_deleted,
            "notifications_deleted": notifications_deleted,
        }
