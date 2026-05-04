"""Tests for RSSScraper — feed cap, date filtering, future-date rejection."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import feedparser

from scrapers.rss_scraper import MAX_ENTRIES_PER_FEED, RSSScraper


def _make_entry(*, title: str, doi: str, days_ago: int):
    """Build a feedparser-like entry (FeedParserDict supports both attr and dict access,
    plus 'key' in entry, which the scraper relies on)."""
    dt = datetime.now() - timedelta(days=days_ago)
    e = feedparser.util.FeedParserDict()
    e["title"] = title
    e["link"] = f"https://doi.org/{doi}"
    e["published"] = dt.strftime("%Y-%m-%d")
    e["published_parsed"] = time.struct_time(dt.timetuple())
    e["summary"] = ""
    e["description"] = ""
    return e


def _entry_with_future_date(days_ahead: int):
    dt = datetime.now() + timedelta(days=days_ahead)
    e = feedparser.util.FeedParserDict()
    e["title"] = f"Future paper {days_ahead}"
    e["link"] = "https://doi.org/10.1234/future"
    e["published"] = dt.strftime("%Y-%m-%d")
    e["published_parsed"] = time.struct_time(dt.timetuple())
    e["summary"] = ""
    e["description"] = ""
    return e


class TestFeedCap:
    """A 6500-entry conference-abstract dump should not be processed entirely."""

    def test_enforces_max_entries_cap(self):
        """Even when 1000 entries pass the date filter, only MAX_ENTRIES_PER_FEED are inspected."""
        entries = [
            _make_entry(title=f"Paper {i}", doi=f"10.1234/paper{i}", days_ago=1)
            for i in range(1000)
        ]
        fake_feed = SimpleNamespace(bozo=False, entries=entries)

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )

        assert len(result) == MAX_ENTRIES_PER_FEED, (
            f"expected cap at {MAX_ENTRIES_PER_FEED}, got {len(result)}"
        )

    def test_small_feed_unchanged(self):
        """Feeds under the cap return all matching entries normally."""
        entries = [
            _make_entry(title=f"Paper {i}", doi=f"10.1234/paper{i}", days_ago=1)
            for i in range(5)
        ]
        fake_feed = SimpleNamespace(bozo=False, entries=entries)

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )
        assert len(result) == 5


class TestDateFiltering:
    def test_old_articles_filtered(self):
        """Articles older than days_back are excluded."""
        entries = [
            _make_entry(title="Recent", doi="10.1234/recent", days_ago=1),
            _make_entry(title="Old", doi="10.1234/old", days_ago=30),
        ]
        fake_feed = SimpleNamespace(bozo=False, entries=entries)

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )
        titles = [a["title"] for a in result]
        assert "Recent" in titles
        assert "Old" not in titles

    def test_far_future_dates_rejected(self):
        """A typo'd or timezone-buggy 2030 date should be rejected, not accepted."""
        entries = [
            _make_entry(title="Recent", doi="10.1234/recent", days_ago=1),
            _entry_with_future_date(days_ahead=400),
        ]
        fake_feed = SimpleNamespace(bozo=False, entries=entries)

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )
        titles = [a["title"] for a in result]
        assert "Recent" in titles
        assert all("Future" not in t for t in titles)

    def test_one_day_future_buffer_allows_timezone_skew(self):
        """A few hours in the future (timezone skew) should still be accepted."""
        entries = [_entry_with_future_date(days_ahead=0)]
        # days_ahead=0 means "now"; combined with the +1 day buffer, this passes
        fake_feed = SimpleNamespace(bozo=False, entries=entries)

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )
        assert len(result) == 1


class TestBozoHandling:
    def test_dead_url_returns_html_no_entries(self):
        """A 404 page parsed as XML produces bozo=True and zero entries — return empty list."""
        fake_feed = SimpleNamespace(
            bozo=True,
            bozo_exception=Exception("not well-formed"),
            entries=[],
        )

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/dead.rss",
                days_back=7,
            )
        assert result == []

    def test_bozo_with_entries_still_processed(self):
        """Some feeds have minor format warnings but still expose valid entries."""
        entries = [_make_entry(title="OK", doi="10.1234/ok", days_ago=1)]
        fake_feed = SimpleNamespace(
            bozo=True, bozo_exception=Exception("warning"), entries=entries
        )

        scraper = RSSScraper()
        with patch("scrapers.rss_scraper.feedparser.parse", return_value=fake_feed):
            result = scraper.fetch_articles(
                url="https://example.com",
                rss_url="https://example.com/feed.rss",
                days_back=7,
            )
        assert len(result) == 1
