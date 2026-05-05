"""Fetcher service — runs scrapers, batch-dedups against DB, persists new articles."""

from __future__ import annotations

import logging
from typing import Any

from database.supabase_client import SupabaseClient
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger("journal_tracker")


class FetcherService:
    """Coordinates article fetching across all scrapers with batch dedup."""

    def __init__(
        self,
        db: SupabaseClient,
        scrapers: dict[str, BaseScraper],
        days_back: int = 7,
    ) -> None:
        self.db = db
        self.scrapers = scrapers
        self.days_back = days_back

    def run(self) -> list[dict[str, Any]]:
        """Fetch from all active journals, dedup, insert. Returns newly-inserted articles."""
        journals = self.db.get_active_journals()
        logger.info(f"Processing {len(journals)} active journals")

        all_new: list[dict[str, Any]] = []
        failed: list[str] = []

        for idx, journal in enumerate(journals, 1):
            logger.info(f"[{idx}/{len(journals)}] {journal['name']} ({journal['category']})")
            try:
                new_articles = self._process_one_journal(journal)
                all_new.extend(new_articles)
            except Exception as e:
                # Belt-and-suspenders: _process_one_journal already catches
                # known failure points, but catch anything that escapes here
                # so a single bad journal can never abort the whole fetch loop.
                logger.error(
                    f"  Unexpected error processing {journal['name']}: {e}",
                    exc_info=True,
                )
                failed.append(journal["name"])
                continue

        if failed:
            logger.warning(f"Failed journals ({len(failed)}): {', '.join(failed)}")
        logger.info(f"Total new articles across all journals: {len(all_new)}")
        return all_new

    def _process_one_journal(self, journal: dict[str, Any]) -> list[dict[str, Any]]:
        scraper_name = journal["scraper_class"]
        scraper = self.scrapers.get(scraper_name)
        if not scraper:
            logger.error(f"  Unknown scraper: {scraper_name}")
            return []

        try:
            fetch_kwargs: dict[str, Any] = {
                "url": journal["url"],
                "rss_url": journal.get("rss_url"),
                "days_back": self.days_back,
            }
            if scraper_name == "PubMedScraper":
                fetch_kwargs["journal_issn"] = journal.get("issn")
                fetch_kwargs["journal_name"] = journal.get("name")

            articles = scraper.fetch_articles(**fetch_kwargs)
            logger.info(f"  Fetched {len(articles)} articles")
        except Exception as e:
            logger.error(f"  Scraper failed: {e}", exc_info=True)
            return []

        if not articles:
            return []

        # Batch dedup — single DB query instead of N
        dois = [a["doi"] for a in articles if a.get("doi")]
        try:
            existing = self.db.existing_dois(dois)
        except Exception as e:
            # Don't let one journal's dedup failure abort the whole fetch loop.
            # We log and skip rather than re-raising so subsequent journals
            # still get processed.
            logger.error(
                f"  Dedup failed ({len(dois)} DOIs): {e}", exc_info=True
            )
            return []
        new_articles = [a for a in articles if a["doi"] not in existing]
        logger.info(f"  {len(new_articles)} new (after dedup)")

        if not new_articles:
            return []

        # Enrich with journal metadata
        for a in new_articles:
            a["journal_id"] = journal["id"]
            a["category"] = journal["category"]
            a["journal_name"] = journal["name"]

        try:
            inserted = self.db.insert_articles(new_articles)
            # Re-attach journal_name (insert doesn't return joined data)
            for i, row in enumerate(inserted):
                if i < len(new_articles):
                    row["journal_name"] = new_articles[i]["journal_name"]
            return inserted
        except Exception as e:
            logger.error(f"  Insert failed: {e}", exc_info=True)
            return []
