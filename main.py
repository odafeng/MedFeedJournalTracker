"""MedFeed Journal Tracker — main entry point.

Pipeline:
  1. Fetch articles from all active journals (with batch dedup)
  1.5. Send raw LINE alerts to subscribers (independent of LLM)
  2. LLM summarize + score (respects daily budget)
  3. Sync new articles to Notion (if configured)
  4. Send curated digest via Telegram
  5. Cleanup old rows

Each stage lives in its own service in `services/`.

Resilience policy
-----------------
Every stage is wrapped in its own try/except so a failure in one never
silences the rest. Errors are accumulated in `stage_errors`; if any
stage failed, the process exits 1 at the end so Render flags the run
as failed in its dashboard, even though all stages were attempted.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from config import Settings
from database.supabase_client import SupabaseClient
from llm.summarizer import LLMSummarizer
from notifier.telegram_notifier import TelegramNotifier
from scrapers.elsevier_scraper import ElsevierScraper
from scrapers.ieee_rss_scraper import IEEERSSScraper
from scrapers.pubmed_scraper import PubMedScraper
from scrapers.rss_scraper import RSSScraper
from services.cleanup_service import CleanupService
from services.fetcher_service import FetcherService
from services.line_alert_service import LineAlertService
from services.llm_service import LLMService
from services.notifier_service import NotifierService
from sync.notion_syncer import NotionSyncer
from utils.logger import setup_logger


def main() -> int:
    start = datetime.now()
    settings = Settings.from_env()
    logger = setup_logger(level=settings.log_level)

    logger.info("=" * 70)
    logger.info(f"MedFeed Journal Tracker — start at {start.isoformat()}")
    logger.info("=" * 70)

    # ---- Init clients ----
    db = SupabaseClient(settings.supabase_url, settings.supabase_key)

    scrapers = {
        "RSSScraper": RSSScraper(),
        "IEEERSSScraper": IEEERSSScraper(),
        "ElsevierScraper": ElsevierScraper(),
        "PubMedScraper": PubMedScraper(api_key=settings.pubmed_api_key),
    }
    logger.info(f"Initialized {len(scrapers)} scrapers")

    stage_errors: list[str] = []
    new_articles: list[dict[str, Any]] = []

    # ---- Stage 1: Fetch ----
    try:
        fetcher = FetcherService(db, scrapers, days_back=settings.days_back)
        new_articles = fetcher.run()
    except Exception as e:
        logger.error(f"Fetch failed (non-fatal): {e}", exc_info=True)
        stage_errors.append("fetch")

    # ---- Stage 1.5: LINE raw alerts (independent of LLM) ----
    # Parallel channel to Telegram — delivers title/authors/journal/DOI to
    # subscribers filtered by category. Runs before LLM so alerts go out
    # even if Claude is down or budget is exhausted.
    # Subscribers live in Supabase; config/subscribers.json is an optional
    # local seed (present on laptop, absent on Render).
    if settings.line_enabled:
        try:
            LineAlertService.seed_from_json(db, settings.line_subscribers_file)
            line_service = LineAlertService(
                settings.line_channel_access_token or "",
                db,
            )
            line_service.run(new_articles)
        except Exception as e:
            logger.error(f"LINE alert failed (non-fatal): {e}", exc_info=True)
            stage_errors.append("line")
    else:
        logger.info("LINE disabled (no LINE_CHANNEL_ACCESS_TOKEN); skipping alerts")

    # ---- Stage 2: LLM (processes *all* unprocessed, not just newly-fetched) ----
    if settings.llm_enabled:
        try:
            summarizer = LLMSummarizer(
                api_key=settings.anthropic_api_key,
                model=settings.llm_model,
            )
            llm_service = LLMService(db, summarizer, daily_budget=settings.llm_daily_budget)
            llm_service.run()
        except Exception as e:
            logger.error(f"LLM stage failed (non-fatal): {e}", exc_info=True)
            stage_errors.append("llm")
    else:
        logger.info("LLM disabled; skipping summarization")

    # ---- Stage 3: Notion sync (best-effort) ----
    if settings.notion_sync_enabled:
        try:
            assert settings.notion_token and settings.notion_database_id
            syncer = NotionSyncer(settings.notion_token, settings.notion_database_id)
            # Sync articles from the last 2 days that are already LLM-processed
            to_sync = db.get_recent_articles_with_journal(days=2, require_llm=True)
            syncer.sync(to_sync)
        except Exception as e:
            logger.error(f"Notion sync failed (non-fatal): {e}", exc_info=True)
            stage_errors.append("notion")
    else:
        logger.info("Notion sync disabled (missing NOTION_TOKEN or NOTION_DATABASE_ID)")

    # ---- Stage 4: Telegram digest ----
    if settings.telegram_enabled:
        try:
            # Use processed articles from the last 24h, not just what we fetched this run
            digest_articles = db.get_recent_articles_with_journal(days=1, require_llm=True)
            notifier = TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)
            notifier_service = NotifierService(db, notifier)
            notifier_service.run(digest_articles)
        except Exception as e:
            logger.error(f"Telegram digest failed (non-fatal): {e}", exc_info=True)
            stage_errors.append("telegram")
    else:
        logger.info("Telegram disabled; skipping digest")

    # ---- Stage 5: Cleanup ----
    try:
        cleanup_service = CleanupService(db, max_articles=10000, max_notifications=500)
        cleanup_service.run()
    except Exception as e:
        logger.error(f"Cleanup failed (non-fatal): {e}", exc_info=True)
        stage_errors.append("cleanup")

    # ---- Summary ----
    end = datetime.now()
    duration = (end - start).total_seconds()
    logger.info("=" * 70)
    logger.info(f"Done in {duration:.1f}s · {len(new_articles)} new articles this run")
    try:
        logger.info(f"Final stats: {db.get_database_stats()}")
    except Exception as e:
        logger.warning(f"Could not fetch final stats: {e}")
    if stage_errors:
        logger.error(f"Stages with errors: {', '.join(stage_errors)}")
    logger.info("=" * 70)

    # Non-zero exit so Render flags the run as failed when any stage erred,
    # even though we attempted (and may have succeeded on) the rest.
    return 1 if stage_errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        import logging
        logging.getLogger("journal_tracker").error(f"Fatal: {e}", exc_info=True)
        sys.exit(1)
