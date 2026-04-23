"""Unit tests for LINE alert formatter."""

from __future__ import annotations

from services.line_alert_service import _format_article, _format_message


def _article(
    title: str = "A novel approach to TME",
    authors: str = "Smith J, Lee K",
    journal: str = "Colorectal Disease",
    doi: str = "10.1111/codi.17250",
) -> dict[str, object]:
    return {
        "title": title,
        "authors": authors,
        "journal_name": journal,
        "doi": doi,
        "category": "CRC",
    }


class TestFormatArticle:
    def test_all_fields_present(self):
        out = _format_article(_article())
        assert "A novel approach to TME" in out
        assert "作者: Smith J, Lee K" in out
        assert "期刊: Colorectal Disease" in out
        assert "🔗 https://doi.org/10.1111/codi.17250" in out

    def test_missing_authors_shows_placeholder(self):
        a = _article(authors="")
        out = _format_article({**a, "authors": None})
        assert "(authors unavailable)" in out

    def test_missing_journal_shows_placeholder(self):
        a = _article()
        del a["journal_name"]
        out = _format_article(a)
        assert "(journal unavailable)" in out

    def test_non_doi_identifier_skips_link(self):
        """PMID-style or empty identifiers shouldn't produce an https://doi.org link."""
        out = _format_article(_article(doi="PMID:12345678"))
        assert "https://doi.org/" not in out

    def test_empty_doi_omits_link_line(self):
        out = _format_article(_article(doi=""))
        assert "🔗" not in out


class TestFormatMessage:
    def test_header_contains_name_category_count(self):
        msg = _format_message(
            subscriber_name="黃醫師",
            category="SDS",
            articles_by_journal={"MedIA": [_article(), _article()]},
        )
        assert "黃醫師" in msg
        assert "SDS" in msg
        assert "2 篇新文章" in msg

    def test_multiple_journals_are_numbered_globally(self):
        msg = _format_message(
            subscriber_name="X",
            category="CRC",
            articles_by_journal={
                "JournalA": [_article(title="First")],
                "JournalB": [_article(title="Second"), _article(title="Third")],
            },
        )
        assert "1. " in msg
        assert "2. " in msg
        assert "3. " in msg
        # Indexing is global, not per-journal
        assert msg.count("1. ") == 1
