"""Format article lists into a digest message with relevance-aware tiering.

Tier 1 (relevance >= 4 in any interest): full Chinese summary + meta
Tier 2 (relevance 2-3 peak):             title + scores + DOI only
Tier 3 (relevance = 1 across the board): skipped entirely
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from html import escape
from typing import Any


def _peak_relevance(article: dict[str, Any]) -> int:
    scores = [
        article.get("relevance_crc") or 0,
        article.get("relevance_sds") or 0,
        article.get("relevance_cvdl") or 0,
    ]
    return max(scores) if scores else 0


def _tier(article: dict[str, Any]) -> int:
    peak = _peak_relevance(article)
    if peak >= 4:
        return 1
    if peak >= 2:
        return 2
    return 3


def format_relevance_line(article: dict[str, Any]) -> str:
    """'CRC 4 · SDS 2 · CV/DL 1' — skipped scores shown as 'n/a'."""

    def _fmt(v: Any) -> str:
        return str(v) if isinstance(v, int) else "n/a"

    return (
        f"CRC {_fmt(article.get('relevance_crc'))} · "
        f"SDS {_fmt(article.get('relevance_sds'))} · "
        f"CV/DL {_fmt(article.get('relevance_cvdl'))}"
    )


def format_digest(articles: Iterable[dict[str, Any]], title: str = "📚 Journal Feed") -> str:
    """Render a digest message for Telegram (HTML parse_mode)."""
    articles = list(articles)
    today = datetime.now().strftime("%Y/%m/%d")

    tier1 = [a for a in articles if _tier(a) == 1]
    tier2 = [a for a in articles if _tier(a) == 2]
    tier3_count = sum(1 for a in articles if _tier(a) == 3)

    header = (
        f"<b>{escape(title)}</b> — {today}\n"
        f"Total: {len(articles)} new · "
        f"Must-read: {len(tier1)} · "
        f"Worth a skim: {len(tier2)} · "
        f"Skipped: {tier3_count}\n"
    )

    sections: list[str] = [header]

    if tier1:
        sections.append("\n<b>🔥 Must-read (relevance ≥ 4)</b>")
        for a in tier1:
            sections.append(_render_full(a))

    if tier2:
        sections.append("\n<b>📖 Worth a skim</b>")
        for a in tier2:
            sections.append(_render_short(a))

    if not tier1 and not tier2:
        sections.append("\n😊 No high-relevance new papers today.")

    sections.append("\n<i>Full archive: check Notion Literature Radar</i>")
    return "\n".join(sections)


def _render_full(a: dict[str, Any]) -> str:
    title = escape(a.get("title", "(no title)"))
    journal = escape(a.get("journal_name", "Unknown"))
    doi = a.get("doi", "")
    url = a.get("url", f"https://doi.org/{doi}" if doi and not doi.startswith("PMID:") else "")
    summary = escape(a.get("summary_zh") or "(no summary)")
    rel = format_relevance_line(a)
    pub_date = a.get("published_date") or ""

    pieces = [
        "",
        f"<b>{title}</b>",
        f"<i>{journal}</i>" + (f" · {pub_date}" if pub_date else ""),
        f"📊 {rel}",
        f"📝 {summary}",
    ]
    if url:
        pieces.append(f'🔗 <a href="{escape(url)}">{escape(doi or "link")}</a>')
    return "\n".join(pieces)


def _render_short(a: dict[str, Any]) -> str:
    title = escape(a.get("title", "(no title)"))
    journal = escape(a.get("journal_name", "Unknown"))
    doi = a.get("doi", "")
    rel = format_relevance_line(a)
    return f"• <b>{title}</b>\n  <i>{journal}</i> · {rel} · <code>{escape(doi)}</code>"
