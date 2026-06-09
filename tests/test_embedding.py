"""Tests for the embedder, embedding service, and the agent's semantic_search."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from agents.query_agent import QueryAgent
from llm.embedder import OpenAIEmbedder
from services.embedding_service import EmbeddingService


def test_build_text_combines_fields():
    text = OpenAIEmbedder.build_text("Title", "中文摘要", "English abstract")
    assert "Title" in text and "中文摘要" in text and "English abstract" in text


def test_build_text_skips_empty():
    assert OpenAIEmbedder.build_text("Only title", None, None) == "Only title"


def test_embedding_service_embeds_and_stores():
    db = MagicMock()
    # One batch, then empty -> loop terminates.
    db.get_articles_without_embedding.side_effect = [
        [{"id": "a1", "title": "T1", "summary_zh": "S1", "abstract": None},
         {"id": "a2", "title": "T2", "summary_zh": None, "abstract": "A2"}],
        [],
    ]
    embedder = MagicMock()
    embedder.embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

    result = EmbeddingService(db, embedder).run()

    assert result == {"embedded": 2, "failed": 0}
    assert db.update_embedding.call_count == 2
    db.update_embedding.assert_any_call("a1", [0.1] * 1536)


def _agent_with_embedder():
    agent = QueryAgent.__new__(QueryAgent)
    agent.client = MagicMock()
    agent.db = MagicMock()
    agent.embedder = MagicMock()
    agent.max_turns = 5
    return agent


def test_semantic_search_tool():
    agent = _agent_with_embedder()
    agent.embedder.embed.return_value = [0.1] * 1536
    agent.db.match_articles.return_value = [
        {"title": "Vector paper", "similarity": 0.91, "doi": "10.1/v"}
    ]

    out = agent._run_tool("semantic_search", {"query": "手術影像", "match_count": 5})

    agent.embedder.embed.assert_called_once_with("手術影像")
    agent.db.match_articles.assert_called_once()
    assert agent.db.match_articles.call_args.kwargs["match_count"] == 5
    assert json.loads(out)[0]["title"] == "Vector paper"


def test_semantic_search_disabled_without_embedder():
    agent = _agent_with_embedder()
    agent.embedder = None
    out = agent._run_tool("semantic_search", {"query": "x"})
    assert "error" in json.loads(out)
