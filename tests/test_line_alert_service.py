"""Unit tests for LINE alert formatter and service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from services.line_alert_service import (
    LineAlertService,
    _format_article,
    _format_message,
)


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
        assert msg.count("1. ") == 1


class TestSeedFromJson:
    def test_missing_file_returns_zero_and_skips_upsert(self, tmp_path: Path):
        db = MagicMock()
        n = LineAlertService.seed_from_json(db, tmp_path / "nope.json")
        assert n == 0
        db.upsert_subscribers.assert_not_called()

    def test_valid_file_upserts_and_returns_count(self, tmp_path: Path):
        db = MagicMock()
        f = tmp_path / "subs.json"
        f.write_text(
            json.dumps({
                "subscribers": [
                    {"name": "Alice", "line_user_id": "Uaaa", "subscribed_category": "CRC"},
                    {"name": "Bob", "line_user_id": "Ubbb", "subscribed_category": "SDS"},
                ]
            }),
            encoding="utf-8",
        )
        n = LineAlertService.seed_from_json(db, f)
        assert n == 2
        db.upsert_subscribers.assert_called_once()
        rows = db.upsert_subscribers.call_args[0][0]
        assert {r["name"] for r in rows} == {"Alice", "Bob"}

    def test_malformed_rows_are_skipped(self, tmp_path: Path):
        db = MagicMock()
        f = tmp_path / "subs.json"
        f.write_text(
            json.dumps({
                "subscribers": [
                    {"name": "Valid", "line_user_id": "Uvvv", "subscribed_category": "CRC"},
                    {"name": "MissingCategory", "line_user_id": "Uxxx"},
                ]
            }),
            encoding="utf-8",
        )
        n = LineAlertService.seed_from_json(db, f)
        assert n == 1
        rows = db.upsert_subscribers.call_args[0][0]
        assert len(rows) == 1
        assert rows[0]["name"] == "Valid"

    def test_malformed_json_returns_zero(self, tmp_path: Path):
        db = MagicMock()
        f = tmp_path / "bad.json"
        f.write_text("not { valid json", encoding="utf-8")
        n = LineAlertService.seed_from_json(db, f)
        assert n == 0
        db.upsert_subscribers.assert_not_called()


class TestRunReadsFromDB:
    def test_no_articles_does_not_hit_db(self):
        db = MagicMock()
        LineAlertService("token", db).run([])
        db.get_active_subscribers.assert_not_called()

    def test_empty_db_subscribers_skips_quietly(self):
        db = MagicMock()
        db.get_active_subscribers.return_value = []
        LineAlertService("token", db).run([_article()])
        db.get_active_subscribers.assert_called_once()

    def test_category_filter_skips_irrelevant_subscribers(self, monkeypatch):
        """SDS subscriber should not receive a CRC-only article batch."""
        db = MagicMock()
        db.get_active_subscribers.return_value = [
            {"name": "CRC-user", "line_user_id": "Ucrc", "subscribed_category": "CRC"},
            {"name": "SDS-user", "line_user_id": "Usds", "subscribed_category": "SDS"},
        ]

        sent_calls: list[tuple[str, str]] = []

        class FakeNotifier:
            def __init__(self, token: str, user_id: str) -> None:
                self._user_id = user_id

            def send(self, message: str) -> bool:
                sent_calls.append((self._user_id, message))
                return True

        monkeypatch.setattr(
            "services.line_alert_service.LineNotifier", FakeNotifier
        )
        LineAlertService("token", db).run([_article()])  # CRC article

        # Only the CRC subscriber gets a send
        assert len(sent_calls) == 1
        assert sent_calls[0][0] == "Ucrc"
