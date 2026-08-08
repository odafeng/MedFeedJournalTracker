"""LLM service — runs summarization + relevance scoring with a daily budget cap."""

from __future__ import annotations

import logging
from typing import Any

from database.supabase_client import SupabaseClient
from llm.summarizer import LLMSummarizer

logger = logging.getLogger("journal_tracker")


class LLMService:
    """Process unprocessed articles through LLM with a hard daily budget."""

    def __init__(
        self,
        db: SupabaseClient,
        summarizer: LLMSummarizer,
        daily_budget: int = 50,
    ) -> None:
        self.db = db
        self.summarizer = summarizer
        self.daily_budget = daily_budget

    def run(self) -> dict[str, int]:
        """Process up to `daily_budget` unprocessed articles.

        Returns: dict with counts of processed/skipped/failed.
        """
        interests = self.db.get_active_interests()
        if not interests:
            logger.warning("No active interests in DB — skipping LLM processing")
            return {"processed": 0, "skipped": 0, "failed": 0}

        logger.info(
            f"LLM processing with {len(interests)} interests: "
            + ", ".join(i["code"] for i in interests)
        )

        unprocessed = self.db.get_unprocessed_articles(limit=self.daily_budget)
        logger.info(f"Found {len(unprocessed)} unprocessed articles (budget: {self.daily_budget})")

        processed = 0
        failed = 0
        for article in unprocessed:
            try:
                self._process_one(article, interests)
                processed += 1
            except Exception as e:
                logger.error(f"LLM failed on article {article.get('id')}: {e}")
                failed += 1
                continue

        logger.info(
            f"LLM done: {processed} processed, {failed} failed, "
            f"{len(unprocessed) - processed - failed} skipped"
        )

        # Whole-stage failure guard.
        # Per-article exceptions are swallowed above so one bad paper can't
        # abort the batch. But if we *attempted* articles and every single one
        # failed, that's not a bad paper — it's a systemic outage (expired
        # ANTHROPIC_API_KEY, exhausted credits, deprecated LLM_MODEL, rate
        # limiting). Left unraised it exits 0, so the run shows green while the
        # Telegram digest (which only includes llm_processed_at IS NOT NULL
        # rows) silently goes empty day after day. Raise so main.py flags the
        # stage, sends the 🚨 alert, and exits non-zero.
        if unprocessed and processed == 0 and failed > 0:
            raise RuntimeError(
                f"LLM stage failed on all {failed} attempted article(s), 0 processed. "
                "Likely a systemic problem (API key / credits / model). "
                "Check ANTHROPIC_API_KEY and LLM_MODEL — the digest will be empty "
                "until this is fixed."
            )

        return {"processed": processed, "skipped": max(0, len(unprocessed) - processed - failed), "failed": failed}

    def _process_one(self, article: dict[str, Any], interests: list[dict[str, Any]]) -> None:
        result = self.summarizer.summarize(
            title=article["title"],
            abstract=article.get("abstract"),
            interests=interests,
        )

        # Map result.relevance codes to DB columns
        rel = result.relevance
        self.db.update_llm_fields(
            article_id=article["id"],
            summary_zh=result.summary_zh,
            relevance_crc=rel.get("CRC", 1),
            relevance_sds=rel.get("SDS", 1),
            relevance_cvdl=rel.get("CVDL", 1),
            llm_model=result.model,
        )
        logger.debug(
            f"  ✓ {article['doi']}: CRC={rel.get('CRC')} SDS={rel.get('SDS')} CVDL={rel.get('CVDL')}"
        )
