"""LINE alert service — pushes raw article notifications to subscribers.

Distinct from ``NotifierService`` (Telegram digest):
- LINE gets every newly-fetched article, filtered only by subscriber category.
- Telegram gets LLM-processed articles with relevance-tier filtering.

Runs right after ``FetcherService`` — does not depend on LLM processing,
so a LLM outage doesn't silence the alert channel.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

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
    """Load subscribers from JSON, filter articles by category, push via LINE.

    Subscribers file format::

        {
          "subscribers": [
            {"name": "...", "line_user_id": "U...", "subscribed_category": "CRC"},
            ...
          ]
        }
    """

    def __init__(
        self,
        channel_access_token: str,
        subscribers_file: Path,
    ) -> None:
        self._token = channel_access_token
        self._subscribers_file = subscribers_file

    def run(self, articles: list[dict[str, Any]]) -> None:
        """Push category-filtered raw alerts to every subscriber."""
        if not articles:
            logger.info("LINE: no new articles this run; skipping")
            return

        subscribers = self._load_subscribers()
        if not subscribers:
            logger.info("LINE: no subscribers configured; skipping")
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

    def _load_subscribers(self) -> list[dict[str, Any]]:
        """Read subscribers.json. Missing file = no subscribers (not an error)."""
        path = self._subscribers_file
        if not path.exists():
            logger.warning(f"LINE: subscribers file not found at {path}")
            return []

        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"LINE: failed to read {path}: {e}")
            return []

        subs = data.get("subscribers", [])
        # Validate required fields; skip malformed rows
        valid: list[dict[str, Any]] = []
        for s in subs:
            if all(k in s for k in ("name", "line_user_id", "subscribed_category")):
                valid.append(s)
            else:
                logger.warning(f"LINE: skipping malformed subscriber row: {s}")
        return valid
