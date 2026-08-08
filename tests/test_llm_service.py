"""Tests for LLMService — per-article resilience vs. whole-stage failure.

One bad paper must not abort the batch, but a batch where *every* attempted
article fails is a systemic outage (expired key / credits / model) and must
surface as a raised error so main.py flags the stage and alerts — instead of
exiting green while the Telegram digest silently goes empty.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.llm_service import LLMService

_INTERESTS = [
    {"code": "CRC", "name": "Colorectal", "description": "..."},
    {"code": "SDS", "name": "SDS", "description": "..."},
    {"code": "CVDL", "name": "CV/DL", "description": "..."},
]


def _article(i: int):
    return {"id": f"a{i}", "title": f"T{i}", "abstract": "abs", "doi": f"10.1/{i}"}


def _ok_result():
    return SimpleNamespace(
        summary_zh="摘要",
        relevance={"CRC": 4, "SDS": 2, "CVDL": 1},
        reasoning="",
        model="test-model",
    )


def _service(db, summarizer, budget=50):
    return LLMService(db, summarizer, daily_budget=budget)


def test_all_articles_fail_raises():
    """Attempted N>0, all failed -> raise so the stage is flagged."""
    db = MagicMock()
    db.get_active_interests.return_value = _INTERESTS
    db.get_unprocessed_articles.return_value = [_article(1), _article(2), _article(3)]

    summarizer = MagicMock()
    summarizer.summarize.side_effect = RuntimeError("authentication_error: 401")

    with pytest.raises(RuntimeError, match="failed on all"):
        _service(db, summarizer).run()

    # update_llm_fields never reached -> llm_processed_at stays null (expected)
    db.update_llm_fields.assert_not_called()


def test_partial_failure_does_not_raise():
    """One bad paper is tolerated as long as at least one succeeds."""
    db = MagicMock()
    db.get_active_interests.return_value = _INTERESTS
    db.get_unprocessed_articles.return_value = [_article(1), _article(2)]

    summarizer = MagicMock()
    summarizer.summarize.side_effect = [RuntimeError("boom"), _ok_result()]

    result = _service(db, summarizer).run()

    assert result == {"processed": 1, "skipped": 0, "failed": 1}
    assert db.update_llm_fields.call_count == 1


def test_all_success_does_not_raise():
    db = MagicMock()
    db.get_active_interests.return_value = _INTERESTS
    db.get_unprocessed_articles.return_value = [_article(1), _article(2)]

    summarizer = MagicMock()
    summarizer.summarize.return_value = _ok_result()

    result = _service(db, summarizer).run()

    assert result == {"processed": 2, "skipped": 0, "failed": 0}


def test_nothing_to_process_does_not_raise():
    """An empty backlog is normal (all caught up), not a failure."""
    db = MagicMock()
    db.get_active_interests.return_value = _INTERESTS
    db.get_unprocessed_articles.return_value = []

    summarizer = MagicMock()

    result = _service(db, summarizer).run()

    assert result == {"processed": 0, "skipped": 0, "failed": 0}
    summarizer.summarize.assert_not_called()


def test_no_active_interests_does_not_raise():
    """No interests short-circuits before any LLM call; not an outage."""
    db = MagicMock()
    db.get_active_interests.return_value = []

    summarizer = MagicMock()

    result = _service(db, summarizer).run()

    assert result == {"processed": 0, "skipped": 0, "failed": 0}
    db.get_unprocessed_articles.assert_not_called()
