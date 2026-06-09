"""Backfill vector embeddings for semantic search.

Embeds every article that doesn't yet have an `embedding`, so the query agent's
semantic_search can find them. Re-runnable and safe to interrupt.

Usage:
    python -m scripts.backfill_embeddings            # embed everything missing
    python -m scripts.backfill_embeddings --limit 500

Env: SUPABASE_*, OPENAI_API_KEY (+ the usual pipeline vars Settings requires).
Cost is tiny — text-embedding-3-small is ~$0.02 per 1M tokens.
"""

from __future__ import annotations

import argparse
import sys

from config import Settings
from database.supabase_client import SupabaseClient
from llm.embedder import OpenAIEmbedder
from services.embedding_service import EmbeddingService
from utils.logger import setup_logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill article embeddings")
    parser.add_argument("--limit", type=int, default=None, help="Max articles (default: all)")
    args = parser.parse_args()

    settings = Settings.from_env()
    logger = setup_logger(level=settings.log_level)

    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY not set — cannot embed. Aborting.")
        return 1

    db = SupabaseClient(settings.supabase_url, settings.supabase_key)
    embedder = OpenAIEmbedder(settings.openai_api_key, model=settings.embedding_model)
    result = EmbeddingService(db, embedder).run(max_articles=args.limit)

    logger.info(f"Embedding backfill done: {result}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
