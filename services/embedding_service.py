"""Embedding service — backfill/maintain article vector embeddings for semantic search."""

from __future__ import annotations

import logging
from typing import Any

from database.supabase_client import SupabaseClient
from llm.embedder import OpenAIEmbedder

logger = logging.getLogger("journal_tracker")


class EmbeddingService:
    """Embed articles that don't yet have a vector, in batches."""

    def __init__(
        self,
        db: SupabaseClient,
        embedder: OpenAIEmbedder,
        batch_size: int = 100,
    ) -> None:
        self.db = db
        self.embedder = embedder
        self.batch_size = batch_size

    def run(self, max_articles: int | None = None) -> dict[str, int]:
        """Embed up to `max_articles` (None = until none remain). Returns counts."""
        embedded = failed = 0
        while True:
            remaining = None if max_articles is None else max_articles - embedded
            if remaining is not None and remaining <= 0:
                break
            limit = self.batch_size if remaining is None else min(self.batch_size, remaining)

            batch = self.db.get_articles_without_embedding(limit=limit)
            if not batch:
                break

            try:
                embedded += self._embed_batch(batch)
            except Exception as e:
                logger.error(f"Embedding batch failed: {e}", exc_info=True)
                failed += len(batch)
                # Avoid an infinite loop if the same batch keeps failing.
                break

        logger.info(f"Embeddings: {embedded} added, {failed} failed")
        return {"embedded": embedded, "failed": failed}

    def _embed_batch(self, batch: list[dict[str, Any]]) -> int:
        texts = [
            OpenAIEmbedder.build_text(a.get("title"), a.get("summary_zh"), a.get("abstract"))
            for a in batch
        ]
        vectors = self.embedder.embed_batch(texts)
        count = 0
        for article, vector in zip(batch, vectors):
            self.db.update_embedding(article["id"], vector)
            count += 1
        return count
