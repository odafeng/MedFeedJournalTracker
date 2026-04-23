"""Tests for BaseScraper utility methods (clean_doi, parse_date, truncate_text)."""

from __future__ import annotations

from scrapers.base_scraper import BaseScraper


class _ConcreteScraper(BaseScraper):
    """Minimal concrete subclass for testing base methods."""

    def fetch_articles(self, url, rss_url=None, days_back=7):
        return []


class TestCleanDoi:
    def setup_method(self):
        self.s = _ConcreteScraper()

    def test_bare_doi(self):
        assert self.s.clean_doi("10.1109/TMI.2025.12345") == "10.1109/TMI.2025.12345"

    def test_doi_with_https_prefix(self):
        assert self.s.clean_doi("https://doi.org/10.1038/s41586-025-00001-1") == "10.1038/s41586-025-00001-1"

    def test_doi_with_http_prefix(self):
        assert self.s.clean_doi("http://doi.org/10.1000/xyz") == "10.1000/xyz"

    def test_doi_with_dx_prefix(self):
        assert self.s.clean_doi("https://dx.doi.org/10.1000/abc") == "10.1000/abc"

    def test_doi_with_doi_colon(self):
        assert self.s.clean_doi("DOI: 10.1038/s41586-025-00001-1") == "10.1038/s41586-025-00001-1"

    def test_doi_with_lowercase_doi_prefix(self):
        assert self.s.clean_doi("doi:10.1000/xyz") == "10.1000/xyz"

    def test_pmid_preserved(self):
        assert self.s.clean_doi("PMID:12345678") == "PMID:12345678"

    def test_pmid_not_confused_with_doi(self):
        result = self.s.clean_doi("PMID:40000000")
        assert result == "PMID:40000000"

    def test_empty_returns_none(self):
        assert self.s.clean_doi("") is None
        assert self.s.clean_doi(None) is None

    def test_extracts_from_dirty_string(self):
        assert self.s.clean_doi("Please see 10.1038/s41586-025-12345 for details") == "10.1038/s41586-025-12345"

    def test_invalid_doi_returns_none(self):
        assert self.s.clean_doi("not-a-doi-at-all") is None

    def test_whitespace_trimmed(self):
        assert self.s.clean_doi("  10.1109/TMI.2025.12345  ") == "10.1109/TMI.2025.12345"


class TestParseDate:
    def setup_method(self):
        self.s = _ConcreteScraper()

    def test_iso_date(self):
        assert self.s.parse_date("2026-04-22") == "2026-04-22"

    def test_slash_date(self):
        assert self.s.parse_date("2026/04/22") == "2026-04-22"

    def test_rss_date_with_tz_offset(self):
        assert self.s.parse_date("Tue, 22 Apr 2026 10:30:00 +0000") == "2026-04-22"

    def test_iso_datetime(self):
        assert self.s.parse_date("2026-04-22T10:30:00") == "2026-04-22"

    def test_iso_datetime_with_z(self):
        assert self.s.parse_date("2026-04-22T10:30:00Z") == "2026-04-22"

    def test_month_name_date(self):
        assert self.s.parse_date("22 Apr 2026") == "2026-04-22"

    def test_full_month_name(self):
        assert self.s.parse_date("22 April 2026") == "2026-04-22"

    def test_us_format(self):
        assert self.s.parse_date("April 22, 2026") == "2026-04-22"

    def test_empty_returns_none(self):
        assert self.s.parse_date("") is None
        assert self.s.parse_date(None) is None

    def test_garbage_returns_none(self):
        assert self.s.parse_date("not a date") is None


class TestTruncateText:
    def setup_method(self):
        self.s = _ConcreteScraper()

    def test_short_text_unchanged(self):
        assert self.s.truncate_text("hello", max_length=100) == "hello"

    def test_long_text_truncated_with_ellipsis(self):
        text = "a" * 100
        result = self.s.truncate_text(text, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_empty(self):
        assert self.s.truncate_text("") == ""
        assert self.s.truncate_text(None) == ""

    def test_strips_whitespace(self):
        assert self.s.truncate_text("  hello  ") == "hello"
