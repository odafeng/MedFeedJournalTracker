"""Tests for FetcherService — ensuring one bad journal can't abort the whole run."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.fetcher_service import FetcherService


def _journal(name: str, scraper_class: str = "RSSScraper", category: str = "CRC"):
    return {
        "id": f"id-{name}",
        "name": name,
        "scraper_class": scraper_class,
        "category": category,
        "url": "https://example.com",
        "rss_url": "https://example.com/feed",
        "issn": "0000-0000",
    }


class TestFetcherResilience:
    def test_dedup_failure_does_not_kill_loop(self):
        """If existing_dois raises (e.g. URL too long), the next journal still gets processed."""
        db = MagicMock()
        db.get_active_journals.return_value = [
            _journal("Journal A"),
            _journal("Journal B"),
            _journal("Journal C"),
        ]
        # First call raises, subsequent calls succeed
        db.existing_dois.side_effect = [
            Exception("URL component 'query' too long"),
            set(),
            set(),
        ]
        db.insert_articles.side_effect = lambda articles: articles

        scraper = MagicMock()
        scraper.fetch_articles.return_value = [
            {"doi": "10.1/x", "title": "T", "url": "u"},
        ]

        svc = FetcherService(db, {"RSSScraper": scraper}, days_back=7)
        result = svc.run()

        # Journals B and C should still produce articles even after A's dedup blew up
        assert db.existing_dois.call_count == 3
        assert len(result) == 2

    def test_scraper_exception_isolated(self):
        """A scraper raising mid-fetch shouldn't leak past _process_one_journal."""
        db = MagicMock()
        db.get_active_journals.return_value = [
            _journal("A"),
            _journal("B"),
        ]
        db.existing_dois.return_value = set()
        db.insert_articles.side_effect = lambda articles: articles

        scraper = MagicMock()
        scraper.fetch_articles.side_effect = [
            RuntimeError("network blew up"),
            [{"doi": "10.1/y", "title": "T", "url": "u"}],
        ]

        svc = FetcherService(db, {"RSSScraper": scraper}, days_back=7)
        result = svc.run()
        assert len(result) == 1

    def test_unknown_scraper_handled(self):
        """A journal with an unknown scraper_class shouldn't crash the run."""
        db = MagicMock()
        db.get_active_journals.return_value = [
            _journal("A", scraper_class="NoSuchScraper"),
            _journal("B", scraper_class="RSSScraper"),
        ]
        db.existing_dois.return_value = set()
        db.insert_articles.side_effect = lambda articles: articles

        scraper = MagicMock()
        scraper.fetch_articles.return_value = [
            {"doi": "10.1/z", "title": "T", "url": "u"},
        ]

        svc = FetcherService(db, {"RSSScraper": scraper}, days_back=7)
        result = svc.run()
        assert len(result) == 1
