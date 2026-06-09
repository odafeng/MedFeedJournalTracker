"""Backfill vector embeddings for semantic search.

Embeds every article that doesn't yet have an `embedding`, so the query agent's
semantic_search can find them. Re-runnable and safe to interrupt.

Usage:
    python -m scripts.backfill_embeddings            # embed everything missing
    python -m scripts.backfill_embeddings --limit 500

Env (only what this task needs — not the full pipeline config):
    SUPABASE_URL, SUPABASE_SERVICE_ROLE (or SUPABASE_KEY / SUPABASE_API_KEY),
    OPENAI_API_KEY, optional EMBEDDING_MODEL.
Cost is tiny — text-embedding-3-small is ~$0.02 per 1M tokens.
"""

from __future__ import annotations

import argparse
import os
import sys

from config.settings import _load_env_files
from database.supabase_client import SupabaseClient
from llm.embedder import OpenAIEmbedder
from services.embedding_service import EmbeddingService
from utils.logger import setup_logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill article embeddings")
    parser.add_argument("--limit", type=int, default=None, help="Max articles (default: all)")
    args = parser.parse_args()

    _load_env_files()
    logger = setup_logger(level=os.getenv("LOG_LEVEL", "INFO"))

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_API_KEY")
    )
    openai_key = os.getenv("OPENAI_API_KEY")

    missing = [
        name for name, val in (
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SERVICE_ROLE", supabase_key),
            ("OPENAI_API_KEY", openai_key),
        )
        if not val
    ]
    if missing:
        logger.error(f"Missing required env vars: {', '.join(missing)}. Aborting.")
        return 1

    db = SupabaseClient(supabase_url, supabase_key)
    embedder = OpenAIEmbedder(
        openai_key, model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    result = EmbeddingService(db, embedder).run(max_articles=args.limit)

    logger.info(f"Embedding backfill done: {result}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
