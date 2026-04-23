"""Supabase client — refactored for batch operations and LLM workflow.

Improvements over v1:
- existing_dois: single batch query instead of N+1
- upsert_journals: native PostgREST upsert (no SELECT-then-UPDATE)
- article_exists now raises on error (no silent swallow)
- cleanup uses RPC functions (no URL length issue)
- new LLM helpers + interests accessor
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from supabase import Client, create_client

logger = logging.getLogger("journal_tracker")


class SupabaseClient:
    """Thin wrapper around supabase-py with project-specific helpers."""

    def __init__(self, url: str, key: str) -> None:
        self.client: Client = create_client(url, key)
        logger.info("Supabase client initialized")

    # ---- journals ----
    def upsert_journals(self, journals: list[dict[str, Any]]) -> None:
        if not journals:
            return
        now = datetime.now().isoformat()
        payload = [
            {
                "name": j["name"],
                "issn": j["issn"],
                "url": j["url"],
                "rss_url": j.get("rss_url"),
                "publisher_type": j["publisher_type"],
                "scraper_class": j["scraper_class"],
                "category": j["category"],
                "is_active": True,
                "updated_at": now,
            }
            for j in journals
        ]
        self.client.table("journals").upsert(payload, on_conflict="issn").execute()
        logger.info(f"Upserted {len(payload)} journals")

    def get_active_journals(self) -> list[dict[str, Any]]:
        response = self.client.table("journals").select("*").eq("is_active", True).execute()
        logger.info(f"Fetched {len(response.data)} active journals")
        return response.data

    # ---- subscribers (legacy, kept for compat) ----
    def upsert_subscribers(self, subscribers: list[dict[str, Any]]) -> None:
        if not subscribers:
            return
        now = datetime.now().isoformat()
        for s in subscribers:
            item = {
                "name": s["name"],
                "line_user_id": s["line_user_id"],
                "subscribed_category": s["subscribed_category"],
                "is_active": True,
                "updated_at": now,
            }
            existing = (
                self.client.table("subscribers")
                .select("id")
                .eq("line_user_id", item["line_user_id"])
                .eq("subscribed_category", item["subscribed_category"])
                .execute()
            )
            if existing.data:
                self.client.table("subscribers").update(item).eq("id", existing.data[0]["id"]).execute()
            else:
                self.client.table("subscribers").insert(item).execute()
        logger.info(f"Synced {len(subscribers)} subscribers")

    def get_active_subscribers(self) -> list[dict[str, Any]]:
        return (
            self.client.table("subscribers").select("*").eq("is_active", True).execute().data
        )

    # ---- articles ----
    def existing_dois(self, dois: list[str]) -> set[str]:
        """Batch check: return the subset of `dois` already in DB. Replaces N+1 `article_exists`."""
        if not dois:
            return set()
        response = self.client.table("articles").select("doi").in_("doi", dois).execute()
        return {row["doi"] for row in response.data}

    def insert_articles(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not articles:
            return []
        payload = [
            {
                "journal_id": a["journal_id"],
                "title": a["title"],
                "doi": a["doi"],
                "url": a["url"],
                "published_date": a.get("published_date"),
                "authors": a.get("authors"),
                "abstract": a.get("abstract"),
                "category": a["category"],
                "discovered_at": datetime.now().isoformat(),
            }
            for a in articles
        ]
        response = self.client.table("articles").insert(payload).execute()
        logger.info(f"Inserted {len(response.data)} articles")
        return response.data

    # ---- LLM workflow ----
    def get_unprocessed_articles(self, limit: int) -> list[dict[str, Any]]:
        """Most recent articles that haven't been LLM-processed."""
        return (
            self.client.table("articles")
            .select("id, title, abstract, journal_id, category, doi, authors, published_date, url")
            .is_("llm_processed_at", "null")
            .order("discovered_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def update_llm_fields(
        self,
        article_id: str,
        summary_zh: str,
        relevance_crc: int,
        relevance_sds: int,
        relevance_cvdl: int,
        llm_model: str,
    ) -> None:
        self.client.table("articles").update({
            "summary_zh": summary_zh,
            "relevance_crc": relevance_crc,
            "relevance_sds": relevance_sds,
            "relevance_cvdl": relevance_cvdl,
            "llm_processed_at": datetime.now().isoformat(),
            "llm_model": llm_model,
        }).eq("id", article_id).execute()

    # ---- interests ----
    def get_active_interests(self) -> list[dict[str, Any]]:
        return (
            self.client.table("interests")
            .select("*")
            .eq("is_active", True)
            .order("code")
            .execute()
            .data
        )

    # ---- recent articles for notify/sync ----
    def get_recent_articles_with_journal(
        self, days: int = 1, require_llm: bool = False
    ) -> list[dict[str, Any]]:
        """Articles in last N days with journal name joined. Optionally only LLM-processed."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        q = (
            self.client.table("articles")
            .select("*, journals(name, category)")
            .gte("discovered_at", cutoff)
        )
        if require_llm:
            q = q.not_.is_("llm_processed_at", "null")
        response = q.order("discovered_at", desc=True).execute()

        out = []
        for row in response.data:
            joined = row.pop("journals", None) or {}
            row["journal_name"] = joined.get("name", "Unknown Journal")
            out.append(row)
        return out

    # ---- notification log ----
    def log_notification(
        self,
        article_id: str,
        subscriber_id: Optional[str],
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        try:
            self.client.table("notifications").insert({
                "article_id": article_id,
                "subscriber_id": subscriber_id,
                "status": status,
                "error_message": error_message,
                "sent_at": datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log notification: {e}")

    # ---- cleanup (via RPC) ----
    def cleanup_articles(self, max_n: int) -> int:
        result = self.client.rpc("cleanup_articles_by_limit", {"max_n": max_n}).execute()
        count = int(result.data) if result.data is not None else 0
        logger.info(f"Articles cleanup: kept {max_n}, deleted {count}")
        return count

    def cleanup_notifications(self, max_n: int) -> int:
        result = self.client.rpc("cleanup_notifications_by_limit", {"max_n": max_n}).execute()
        count = int(result.data) if result.data is not None else 0
        logger.info(f"Notifications cleanup: kept {max_n}, deleted {count}")
        return count

    def get_database_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for table in ("journals", "subscribers", "articles", "notifications", "interests"):
            try:
                response = self.client.table(table).select("id", count="exact").execute()
                count = (
                    response.count
                    if hasattr(response, "count") and response.count is not None
                    else len(response.data)
                )
                stats[table] = count
            except Exception as e:
                logger.warning(f"Failed to count {table}: {e}")
                stats[table] = -1
        return stats
