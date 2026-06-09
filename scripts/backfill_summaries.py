"""Backfill Chinese summaries for older articles.

Roughly 500 historical articles have no `summary_zh`, which makes them
invisible to the LINE query agent's Chinese free-text search. This one-off
(re-runnable) script finds articles missing a summary and processes them
through the same LLMSummarizer the daily pipeline uses.

Usage:
    python -m scripts.backfill_summaries --limit 100
    python -m scripts.backfill_summaries --all          # ignore the limit, loop until done

Env vars: same as the pipeline (SUPABASE_*, ANTHROPIC_API_KEY, LLM_MODEL).
Run it a few times (or with --all) to clear the whole backlog; each article
is one cheap Sonnet call.
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import Settings
from database.supabase_client import SupabaseClient
from llm.summarizer import LLMSummarizer
from utils.logger import setup_logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing summary_zh")
    parser.add_argument("--limit", type=int, default=100, help="Max articles per run (batch size)")
    parser.add_argument("--all", action="store_true", help="Keep looping until no rows remain")
    args = parser.parse_args()

    settings = Settings.from_env()
    logger = setup_logger(level=settings.log_level)

    db = SupabaseClient(settings.supabase_url, settings.supabase_key)
    summarizer = LLMSummarizer(api_key=settings.anthropic_api_key, model=settings.llm_model)

    interests = db.get_active_interests()
    if not interests:
        logger.error("No active interests in DB — cannot score articles. Aborting.")
        return 1

    total_done = total_failed = 0
    while True:
        batch = db.get_articles_without_summary(limit=args.limit)
        if not batch:
            logger.info("No articles left without a summary.")
            break

        logger.info(f"Processing batch of {len(batch)} articles...")
        for article in batch:
            try:
                result = summarizer.summarize(
                    title=article["title"],
                    abstract=article.get("abstract"),
                    interests=interests,
                )
                rel = result.relevance
                db.update_llm_fields(
                    article_id=article["id"],
                    summary_zh=result.summary_zh,
                    relevance_crc=rel.get("CRC", 1),
                    relevance_sds=rel.get("SDS", 1),
                    relevance_cvdl=rel.get("CVDL", 1),
                    llm_model=result.model,
                )
                total_done += 1
            except Exception as e:
                logger.error(f"Failed on {article.get('doi') or article.get('id')}: {e}")
                total_failed += 1

        logger.info(f"Running totals — done: {total_done}, failed: {total_failed}")
        if not args.all:
            break

    logger.info(f"Backfill complete. {total_done} summarized, {total_failed} failed.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
