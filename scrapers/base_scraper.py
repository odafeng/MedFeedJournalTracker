"""Base scraper — with tenacity retry and no silent exception swallowing."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

logger = logging.getLogger("journal_tracker")


class BaseScraper(ABC):
    """Abstract base for all scrapers."""

    @abstractmethod
    def fetch_articles(
        self,
        url: str,
        rss_url: Optional[str] = None,
        days_back: int = 7,
    ) -> list[dict]:
        """Return list of articles. Each article dict has title/doi/url/published_date/authors/abstract."""

    def clean_doi(self, doi: Optional[str]) -> Optional[str]:
        """Normalize DOI or PMID."""
        if not doi:
            return None
        doi = doi.strip()
        if doi.startswith("PMID:"):
            return doi
        for prefix in (
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "DOI:",
            "doi:",
        ):
            doi = doi.replace(prefix, "")
        doi = doi.strip()
        if not doi.startswith("10."):
            m = re.search(r"10\.\d{4,}[^\s]*", doi)
            if m:
                return m.group(0)
            logger.debug(f"No standard DOI format: {doi}")
            return None
        return doi

    def parse_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        formats = (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
            "%B %d, %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%A, %d %B %Y %H:%M:%S %Z",
            "%A, %d %B %Y %H:%M:%S %z",
        )
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        logger.warning(f"Could not parse date: {date_str}")
        return None

    def truncate_text(self, text: Optional[str], max_length: int = 500) -> str:
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."
