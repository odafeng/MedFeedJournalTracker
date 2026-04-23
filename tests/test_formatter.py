"""Tests for notifier.formatter (relevance tiering logic)."""

from __future__ import annotations

from notifier.formatter import _peak_relevance, _tier, format_digest, format_relevance_line


def _article(crc=1, sds=1, cvdl=1, **kwargs):
    base = {
        "title": "Some title",
        "doi": "10.1000/x",
        "journal_name": "Test Journal",
        "relevance_crc": crc,
        "relevance_sds": sds,
        "relevance_cvdl": cvdl,
        "summary_zh": "摘要一。摘要二。摘要三。",
        "url": "https://doi.org/10.1000/x",
        "published_date": "2026-04-22",
    }
    base.update(kwargs)
    return base


class TestTiering:
    def test_peak_relevance(self):
        assert _peak_relevance(_article(crc=4, sds=2, cvdl=1)) == 4
        assert _peak_relevance(_article(crc=1, sds=1, cvdl=5)) == 5

    def test_tier_must_read(self):
        assert _tier(_article(crc=4, sds=1, cvdl=1)) == 1
        assert _tier(_article(crc=1, sds=1, cvdl=5)) == 1

    def test_tier_skim(self):
        assert _tier(_article(crc=3, sds=2, cvdl=1)) == 2
        assert _tier(_article(crc=2, sds=2, cvdl=2)) == 2

    def test_tier_skip(self):
        assert _tier(_article(crc=1, sds=1, cvdl=1)) == 3

    def test_missing_scores_default_to_zero(self):
        assert _peak_relevance({"title": "x"}) == 0


class TestFormatDigest:
    def test_empty_list(self):
        msg = format_digest([])
        assert "No high-relevance" in msg
        assert "0 new" in msg

    def test_must_read_full_rendering(self):
        article = _article(crc=5)
        msg = format_digest([article])
        assert "Must-read" in msg
        assert "摘要一" in msg
        assert "Test Journal" in msg

    def test_skim_tier_short_rendering(self):
        article = _article(crc=2)
        msg = format_digest([article])
        assert "Worth a skim" in msg
        assert "摘要一" not in msg  # summary not rendered for skim tier

    def test_tier3_skipped(self):
        article = _article(crc=1, sds=1, cvdl=1)
        msg = format_digest([article])
        assert "Skipped: 1" in msg
        assert "Some title" not in msg  # title not rendered at all

    def test_html_escaped(self):
        article = _article(title="<script>alert(1)</script>")
        msg = format_digest([_article(crc=5, **{"title": "<b>x</b>"})])
        assert "<b>x</b>" not in msg.replace("<b>📚", "")  # our own <b> tags stay; title tags escaped
        # Our title tag is now wrapped in escaped form
        assert "&lt;b&gt;x&lt;/b&gt;" in msg


class TestRelevanceLine:
    def test_all_scores(self):
        assert "CRC 4" in format_relevance_line(_article(crc=4, sds=2, cvdl=1))

    def test_missing_scores_shown_as_na(self):
        line = format_relevance_line({"relevance_crc": 3})
        assert "n/a" in line
