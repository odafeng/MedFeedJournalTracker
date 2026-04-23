"""LINE alert service — pushes raw article notifications to subscribers.

Distinct from ``NotifierService`` (Telegram digest):
- LINE gets every newly-fetched article, filtered only by subscriber category.
- Telegram gets LLM-processed articles with relevance-tier filtering.

Runs right after ``FetcherService`` — does not depend on LLM processing,
so a LLM outage doesn't silence the alert channel.

Subscriber storage
------------------
Subscribers live in the Supabase ``subscribers`` table — this is the
authoritative source on Render (and anywhere else cloud-hosted), since
the container filesystem is ephemeral.

``config/subscribers.json`` is a **local-dev convenience**: if the file
exists when main.py runs, its contents are upserted into Supabase via
``seed_from_json`` before alerts fire. That way you can edit the JSON
on your laptop, run main.py once, and Render's next cron pulls the
updated list from the DB. On Render itself the file is absent — the
DB already has what it needs.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from database.supabase_client import SupabaseClient
from notifier.line_notifier import LineNotifier

logger = logging.getLogger("journal_tracker")


def _format_article(article: dict[str, Any]) -> str:
    """Format one article for LINE: title + authors + journal + DOI link."""
    title = article.get("title", "(no title)")
    authors = article.get("authors") or "(authors unavailable)"
    journal = article.get("journal_name", "(journal unavailable)")
    doi = article.get("doi") or ""
    doi_link = f"https://doi.org/{doi}" if doi and doi.startswith("10.") else (doi or "")

    parts = [title, f"作者: {authors}", f"期刊: {journal}"]
    if doi_link:
        parts.append(f"🔗 {doi_link}")
    return "\n".join(parts)


def _format_message(
    subscriber_name: str,
    category: str,
    articles_by_journal: dict[str, list[dict[str, Any]]],
) -> str:
    """Build the full LINE message body for one subscriber + category."""
    total = sum(len(v) for v in articles_by_journal.values())
    today = datetime.now().strftime("%Y/%m/%d")

    header = (
        f"📚 {subscriber_name} 的期刊更新 ({today})\n"
        f"類別: {category} · {total} 篇新文章\n"
    )

    blocks: list[str] = []
    idx = 1
    for journal_name in sorted(articles_by_journal):
        for article in articles_by_journal[journal_name]:
            blocks.append(f"{idx}. {_format_article(article)}")
            idx += 1

    return header + "\n" + "\n\n".join(blocks)


class LineAlertService:
    """Read active subscribers from Supabase, filter articles by category,
    push via LINE. Subscribers are managed in the DB; see ``seed_from_json``
    for the local-dev workflow that upserts ``config/subscribers.json``.
    """

    def __init__(self, channel_access_token: str, db: SupabaseClient) -> None:
        self._token = channel_access_token
        self._db = db

    @staticmethod
    def seed_from_json(db: SupabaseClient, path: Path) -> int:
        """Upsert the subscribers listed in ``path`` (JSON) into Supabase.

        Returns the number of rows processed (0 if the file is missing).
        Idempotent — can be called every run; upsert dedups by
        (line_user_id, subscribed_category).
        """
        if not path.exists():
            logger.info(f"LINE seed: {path} not found — skipping (DB already authoritative)")
            return 0

        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"LINE seed: failed to read {path}: {e}")
            return 0

        raw = data.get("subscribers", [])
        valid: list[dict[str, Any]] = []
        for s in raw:
            if all(k in s for k in ("name", "line_user_id", "subscribed_category")):
                valid.append(s)
            else:
                logger.warning(f"LINE seed: skipping malformed row: {s}")

        if not valid:
            return 0

        db.upsert_subscribers(valid)
        logger.info(f"LINE seed: upserted {len(valid)} rows from {path} to Supabase")
        return len(valid)

    def run(self, articles: list[dict[str, Any]]) -> None:
        """Push category-filtered raw alerts to every active subscriber in DB."""
        if not articles:
            logger.info("LINE: no new articles this run; skipping")
            return

        subscribers = self._db.get_active_subscribers()
        if not subscribers:
            logger.info("LINE: no active subscribers in DB; skipping")
            return

        # Group articles by category once (not per subscriber)
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for a in articles:
            cat = a.get("category")
            if cat:
                by_category[cat].append(a)

        success = 0
        failed = 0
        for sub in subscribers:
            name = sub["name"]
            user_id = sub["line_user_id"]
            category = sub["subscribed_category"]

            relevant = by_category.get(category, [])
            if not relevant:
                logger.info(f"LINE: no {category} articles for {name}; skipping")
                continue

            # Group by journal for nicer display
            by_journal: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for a in relevant:
                by_journal[a.get("journal_name", "(unknown)")].append(a)

            message = _format_message(name, category, dict(by_journal))

            try:
                ok = LineNotifier(self._token, user_id).send(message)
            except Exception as e:
                logger.error(f"LINE send raised for {name}: {e}")
                ok = False

            if ok:
                success += 1
                logger.info(f"LINE: sent {len(relevant)} articles to {name} ({category})")
            else:
                failed += 1

        logger.info(f"LINE digest complete: {success} sent, {failed} failed")
