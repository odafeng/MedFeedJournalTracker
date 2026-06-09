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
        zero_raw: list[str] = []   # journals whose feed returned nothing (maybe broken)

        for idx, journal in enumerate(journals, 1):
            logger.info(f"[{idx}/{len(journals)}] {journal['name']} ({journal['category']})")
            try:
                new_articles, raw_count = self._process_one_journal(journal)
                all_new.extend(new_articles)
                if raw_count == 0:
                    zero_raw.append(journal["name"])
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
        # A feed returning zero raw items can be legitimate, but if a large share
        # of feeds are empty it usually signals a systemic break (blocked IP,
        # parser regression). Surface it so it doesn't fail silently.
        if zero_raw:
            logger.warning(
                f"{len(zero_raw)}/{len(journals)} journals returned 0 raw articles: "
                f"{', '.join(zero_raw)}"
            )
            if journals and len(zero_raw) >= max(3, len(journals) // 2):
                logger.error(
                    "More than half of feeds returned nothing — likely a systemic "
                    "fetch problem, not just quiet weeks."
                )
        logger.info(f"Total new articles across all journals: {len(all_new)}")
        return all_new

    def _process_one_journal(self, journal: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        scraper_name = journal["scraper_class"]
        scraper = self.scrapers.get(scraper_name)
        if not scraper:
            logger.error(f"  Unknown scraper: {scraper_name}")
            return [], 0

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
            return [], 0

        raw_count = len(articles)
        if not articles:
            return [], 0

        try:
            new_articles = self._dedup(journal, articles)
        except Exception as e:
            # Don't let one journal's dedup failure abort the whole fetch loop.
            logger.error(f"  Dedup failed: {e}", exc_info=True)
            return [], raw_count
        logger.info(f"  {len(new_articles)} new (after dedup)")

        if not new_articles:
            return [], raw_count

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
            return inserted, raw_count
        except Exception as e:
            logger.error(f"  Insert failed: {e}", exc_info=True)
            return [], raw_count

    def _dedup(
        self, journal: dict[str, Any], articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop articles already in the DB.

        DOI is the primary key for dedup. Articles arriving without a usable DOI
        (some RSS feeds) fall back to a normalized (journal, title) match so they
        aren't re-inserted on every run.
        """
        with_doi = [a for a in articles if a.get("doi")]
        no_doi = [a for a in articles if not a.get("doi")]

        new: list[dict[str, Any]] = []

        if with_doi:
            existing = self.db.existing_dois([a["doi"] for a in with_doi])
            new.extend(a for a in with_doi if a["doi"] not in existing)

        if no_doi:
            titles = [a.get("title", "") for a in no_doi]
            existing_titles = self.db.existing_titles(journal["id"], titles)
            seen_this_run: set[str] = set()
            added = 0
            for a in no_doi:
                title = a.get("title", "")
                if not title or title in existing_titles or title in seen_this_run:
                    continue
                seen_this_run.add(title)
                new.append(a)
                added += 1
            if len(no_doi) - added:
                logger.info(f"  {len(no_doi) - added} no-DOI duplicates skipped (title match)")

        return new
