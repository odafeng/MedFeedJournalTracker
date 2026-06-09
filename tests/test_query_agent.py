"""Tests for QueryAgent's agentic loop (mocked Anthropic client + RPC)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from agents.query_agent import SQL_TOOL, QueryAgent


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_block(sql: str, block_id: str = "t1"):
    return SimpleNamespace(
        type="tool_use", name="execute_sql", id=block_id,
        input={"sql": sql, "explanation": "test"},
    )


def _make_agent():
    agent = QueryAgent.__new__(QueryAgent)  # bypass __init__ (no real API key)
    agent.client = MagicMock()
    agent.db = MagicMock()
    agent.embedder = None
    agent.tools = [SQL_TOOL]
    agent.max_turns = 5
    return agent


def test_ask_runs_tool_then_returns_text():
    agent = _make_agent()
    # RPC returns one row
    agent.db.client.rpc.return_value.execute.return_value.data = [{"title": "Paper A"}]

    # Turn 1: model asks to run SQL. Turn 2: model answers.
    agent.client.messages.create.side_effect = [
        SimpleNamespace(stop_reason="tool_use", content=[_tool_block("SELECT 1")]),
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("找到 1 篇：Paper A")]),
    ]

    answer = agent.ask("有什麼文章？")
    assert answer == "找到 1 篇：Paper A"
    # The SQL was executed via the RPC
    agent.db.client.rpc.assert_called_once()
    args = agent.db.client.rpc.call_args[0]
    assert args[0] == "execute_readonly_query"


def test_ask_prepends_history():
    agent = _make_agent()
    agent.client.messages.create.side_effect = [
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")]),
    ]
    history = [
        {"role": "user", "content": "第一個問題"},
        {"role": "assistant", "content": "第一個回答"},
    ]
    agent.ask("那第二篇呢？", history=history)

    sent = agent.client.messages.create.call_args.kwargs["messages"]
    assert sent[0]["content"] == "第一個問題"
    assert sent[-1]["content"] == "那第二篇呢？"


def test_execute_sql_serializes_error():
    agent = _make_agent()
    agent.db.client.rpc.side_effect = RuntimeError("boom")
    out = agent._execute_sql("SELECT 1")
    assert json.loads(out)["error"] == "boom"
