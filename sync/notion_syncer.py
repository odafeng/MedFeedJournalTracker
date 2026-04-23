"""Notion sync — Supabase → Notion, append-only.

Strategy:
- For each newly-LLM-processed article in the last N days, check if its DOI
  already exists in the Notion database. If not, create a new page.
- If it exists, skip (append-only, no update). This matches the user's choice
  of keeping Notion as a long-term archive even after Supabase cleanup.
- Never deletes Notion rows.
"""

from __future__ import annotations

import logging
from typing import Any

from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("journal_tracker")


class NotionSyncer:
    """Sync Supabase articles into a Notion database (insert-if-not-exists)."""

    def __init__(self, token: str, database_id: str) -> None:
        self.client = NotionClient(auth=token)
        self.database_id = database_id

    def sync(self, articles: list[dict[str, Any]]) -> dict[str, int]:
        """Sync a batch of articles. Returns counts: {created, skipped, failed}."""
        created = 0
        skipped = 0
        failed = 0

        for a in articles:
            doi = a.get("doi")
            if not doi:
                continue
            try:
                if self._exists(doi):
                    skipped += 1
                    continue
                self._create_page(a)
                created += 1
            except Exception as e:
                logger.error(f"Notion sync failed for {doi}: {e}")
                failed += 1
                continue

        logger.info(f"Notion sync: {created} created, {skipped} already existed, {failed} failed")
        return {"created": created, "skipped": skipped, "failed": failed}

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(APIResponseError),
    )
    def _exists(self, doi: str) -> bool:
        """Query Notion DB for an existing row with this DOI."""
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={"property": "DOI", "rich_text": {"equals": doi}},
            page_size=1,
        )
        return len(response.get("results", [])) > 0

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(APIResponseError),
    )
    def _create_page(self, article: dict[str, Any]) -> None:
        properties = self._article_to_properties(article)
        self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )

    @staticmethod
    def _rich_text(text: str | None, limit: int = 2000) -> list[dict[str, Any]]:
        if not text:
            return []
        t = text[:limit]
        return [{"type": "text", "text": {"content": t}}]

    def _article_to_properties(self, a: dict[str, Any]) -> dict[str, Any]:
        title = a.get("title") or "(no title)"
        # Notion title length limit is 2000 chars
        props: dict[str, Any] = {
            "Title": {"title": [{"type": "text", "text": {"content": title[:2000]}}]},
        }

        if a.get("doi"):
            props["DOI"] = {"rich_text": self._rich_text(a["doi"])}

        journal_name = a.get("journal_name")
        if journal_name:
            props["Journal"] = {"select": {"name": journal_name[:100]}}

        if a.get("category"):
            props["Category"] = {"multi_select": [{"name": a["category"]}]}

        if a.get("published_date"):
            props["Published"] = {"date": {"start": a["published_date"]}}

        for (col, prop) in (("relevance_crc", "CRC"), ("relevance_sds", "SDS"), ("relevance_cvdl", "CV/DL")):
            v = a.get(col)
            if isinstance(v, int):
                props[prop] = {"number": v}

        if a.get("summary_zh"):
            props["中文摘要"] = {"rich_text": self._rich_text(a["summary_zh"])}

        if a.get("url"):
            props["URL"] = {"url": a["url"]}

        if a.get("authors"):
            props["Authors"] = {"rich_text": self._rich_text(a["authors"])}

        # Read? defaults unchecked (Notion default); don't set it

        return props
