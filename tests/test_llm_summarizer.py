"""Unit tests for the LLM summarizer's parser (no API calls)."""

from __future__ import annotations

import pytest

from llm.summarizer import LLMSummarizer


@pytest.fixture
def summarizer():
    return LLMSummarizer(api_key="dummy-key-not-used", model="test-model")


class TestParseResponse:
    def test_valid_json(self, summarizer):
        raw = '{"summary_zh": "一句話", "relevance": {"CRC": 4, "SDS": 2, "CVDL": 1}, "reasoning": "..."}'
        parsed = summarizer._parse_response(raw, ["CRC", "SDS", "CVDL"])
        assert parsed["summary_zh"] == "一句話"
        assert parsed["relevance"] == {"CRC": 4, "SDS": 2, "CVDL": 1}

    def test_strips_markdown_fence(self, summarizer):
        raw = '```json\n{"summary_zh": "x", "relevance": {"CRC": 3, "SDS": 3, "CVDL": 3}}\n```'
        parsed = summarizer._parse_response(raw, ["CRC", "SDS", "CVDL"])
        assert parsed["relevance"]["CRC"] == 3

    def test_strips_bare_fence(self, summarizer):
        raw = '```\n{"summary_zh": "x", "relevance": {"CRC": 3, "SDS": 3, "CVDL": 3}}\n```'
        parsed = summarizer._parse_response(raw, ["CRC", "SDS", "CVDL"])
        assert parsed["summary_zh"] == "x"

    def test_clamps_out_of_range(self, summarizer):
        raw = '{"summary_zh": "x", "relevance": {"CRC": 99, "SDS": 0, "CVDL": 3}}'
        parsed = summarizer._parse_response(raw, ["CRC", "SDS", "CVDL"])
        # invalid values (not 1-5 int) default to 1
        assert parsed["relevance"]["CRC"] == 1
        assert parsed["relevance"]["SDS"] == 1
        assert parsed["relevance"]["CVDL"] == 3

    def test_missing_code_defaults_to_1(self, summarizer):
        raw = '{"summary_zh": "x", "relevance": {"CRC": 4}}'
        parsed = summarizer._parse_response(raw, ["CRC", "SDS", "CVDL"])
        assert parsed["relevance"]["CRC"] == 4
        assert parsed["relevance"]["SDS"] == 1
        assert parsed["relevance"]["CVDL"] == 1

    def test_invalid_json_raises(self, summarizer):
        import json
        with pytest.raises(json.JSONDecodeError):
            summarizer._parse_response("not json", ["CRC"])

    def test_missing_summary_raises(self, summarizer):
        with pytest.raises(ValueError, match="summary_zh"):
            summarizer._parse_response('{"relevance": {"CRC": 3}}', ["CRC"])

    def test_missing_relevance_raises(self, summarizer):
        with pytest.raises(ValueError, match="relevance"):
            summarizer._parse_response('{"summary_zh": "x"}', ["CRC"])
