"""Tests for SupabaseClient.existing_dois batching behavior.

The previous implementation would put 6000+ DOIs into a single PostgREST
IN clause, blowing past httpx's URL length limit. These tests verify the
chunked replacement.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from database.supabase_client import SupabaseClient


def _make_client_with_mock_table(found_dois: set[str]):
    """Build a SupabaseClient whose .client.table().select().in_().execute()
    returns whatever subset of the queried chunk is in found_dois."""
    client = SupabaseClient.__new__(SupabaseClient)  # bypass __init__ (no real network)

    captured_chunks: list[list[str]] = []

    def fake_execute_for_chunk(chunk):
        return SimpleNamespace(data=[{"doi": d} for d in chunk if d in found_dois])

    class FakeQuery:
        def __init__(self):
            self._last_chunk: list[str] = []

        def select(self, *_args, **_kwargs):
            return self

        def in_(self, _column, values):
            self._last_chunk = list(values)
            captured_chunks.append(self._last_chunk)
            return self

        def execute(self):
            return fake_execute_for_chunk(self._last_chunk)

    fake_table_client = MagicMock()
    fake_table_client.table.return_value = FakeQuery()
    client.client = fake_table_client

    return client, captured_chunks


class TestExistingDoisBatching:
    def test_empty_returns_empty(self):
        client, _ = _make_client_with_mock_table(set())
        assert client.existing_dois([]) == set()

    def test_small_list_one_chunk(self):
        found = {"10.1/a", "10.1/b"}
        dois = ["10.1/a", "10.1/b", "10.1/c"]
        client, captured = _make_client_with_mock_table(found)
        result = client.existing_dois(dois, chunk_size=100)
        assert result == found
        assert len(captured) == 1

    def test_large_list_chunked(self):
        """6000 DOIs at chunk_size=100 should produce 60 chunks, never one giant query."""
        dois = [f"10.1/p{i}" for i in range(6000)]
        # Mark every 100th as existing
        found = {d for i, d in enumerate(dois) if i % 100 == 0}
        client, captured = _make_client_with_mock_table(found)

        result = client.existing_dois(dois, chunk_size=100)

        assert result == found
        assert len(captured) == 60
        # No chunk exceeds the configured size
        assert all(len(c) <= 100 for c in captured)

    def test_dedupes_input(self):
        """If the same DOI appears 1000 times in input, it shouldn't bloat the query."""
        dois = ["10.1/a"] * 1000 + ["10.1/b"] * 1000
        client, captured = _make_client_with_mock_table({"10.1/a", "10.1/b"})

        result = client.existing_dois(dois, chunk_size=100)

        assert result == {"10.1/a", "10.1/b"}
        # After dedup we should issue only one chunk (2 unique DOIs)
        total_queried = sum(len(c) for c in captured)
        assert total_queried == 2

    def test_filters_falsy_dois(self):
        """None and empty strings shouldn't be sent to the DB."""
        dois = ["10.1/a", None, "", "10.1/b"]
        client, captured = _make_client_with_mock_table({"10.1/a"})

        result = client.existing_dois(dois)

        assert result == {"10.1/a"}
        for chunk in captured:
            assert all(d for d in chunk)
