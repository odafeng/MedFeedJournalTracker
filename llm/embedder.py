"""OpenAI embeddings for semantic search.

Produces vectors for article text (title + Chinese summary + abstract) and for
user queries, so the query agent can do meaning-based retrieval via pgvector.

Model: text-embedding-3-small (1536 dims) — cheap and good enough for this
retrieval task. Set OPENAI_API_KEY to enable.
"""

from __future__ import annotations

import logging

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("journal_tracker")

EMBED_DIM = 1536


class OpenAIEmbedder:
    """Thin wrapper around the OpenAI embeddings API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @staticmethod
    def build_text(title: str | None, summary_zh: str | None, abstract: str | None) -> str:
        """Combine the most informative fields into one string to embed."""
        parts = [p for p in (title, summary_zh, abstract) if p]
        text = "\n".join(parts).strip()
        # Keep well under the model's token limit; titles+summaries are short.
        return text[:8000] if text else (title or "")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def embed(self, text: str) -> list[float]:
        resp = self.client.embeddings.create(model=self.model, input=text or " ")
        return resp.data[0].embedding

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts in one request (OpenAI accepts a list)."""
        if not texts:
            return []
        cleaned = [t or " " for t in texts]
        resp = self.client.embeddings.create(model=self.model, input=cleaned)
        # API preserves input order
        return [d.embedding for d in resp.data]
