# MedFeed v2 Deployment Guide

This document covers the complete migration from v1 → v2 and the one-time setup
needed for LLM summarization + Telegram notifications + Notion sync.

---

## What changed in v2

| Area | v1 | v2 |
|---|---|---|
| Dependency management | `requirements.txt` | `pyproject.toml` + `uv` |
| `main.py` | 441 lines, 9 concerns | ~90 lines, pure orchestration |
| DB dedup | N+1 queries (`article_exists` per row) | Single batch query via `existing_dois` |
| Journal upsert | SELECT-then-UPDATE per row | Native PostgREST `upsert` |
| DB cleanup | URL-based `NOT IN` (fails above ~100 rows) | RPC functions `cleanup_articles_by_limit` |
| LLM | none | Claude Sonnet 4.5 summary + 3-axis relevance |
| Push channel | LINE (200/mo quota) | Telegram (no quota) |
| Notion | none | Append-only DB sync |
| Tests | `test_scrapers.py` manual | `pytest` 46 tests |
| CI | none | GitHub Actions: lint + test on PR, weekly integration |
| Branches | direct push to `main` | `feat/xxx` → `dev` → `main` |

---

## Part 1: Supabase (DONE already — verify)

Phase 1 migrations were applied live via MCP on 2026-04-22. Login to Supabase
and verify:

1. **Project MedFeed** → Table Editor → `articles` → confirm 6 new columns:
   `summary_zh`, `relevance_crc`, `relevance_sds`, `relevance_cvdl`,
   `llm_processed_at`, `llm_model`.
2. **`interests` table** exists with 3 rows (CRC, SDS, CVDL).
3. **SQL Editor** → run `SELECT proname FROM pg_proc WHERE proname LIKE 'cleanup_%_by_limit'` → should return 2 rows.

If anything is missing: run `medfeed_backup_20260422/rollback.sql`, then start
over. Otherwise: proceed.

**Editing LLM scoring criteria in the future:**
Open `interests` table in Supabase, edit the `description` field of any row.
The change takes effect on the next cron run — no code deploy needed.

---

## Part 2: Notion database (DONE already — confirm IDs)

**Created under:** PhD Dissertation → 📡 Literature Radar → 📚 Journal Feed

- **Database ID:** `d2b8807f-8d79-42e0-9fc5-542b5723426b`
- **Data source ID:** `8f59a347-6823-477d-95c0-e1b7bb1e6e6c`
- **URL:** https://www.notion.so/d2b8807f8d7942e09fc5542b5723426b

**Views created:**
- 🔥 Must Read (any relevance ≥ 4 AND unread)
- 📅 Recent (all, sorted by Published desc)
- 🗂 By Journal (grouped by source)
- ✅ Read (archive view)

### Grant the Notion integration access

Your `NOTION_TOKEN` must belong to an integration that has **edit access** to the
📚 Journal Feed database. To grant:

1. Open the 📚 Journal Feed page in Notion.
2. Click `⋯` (top right) → **Add connections** → select your integration.
3. Choose "Can edit" permission.

If you don't have an integration token yet:
1. https://www.notion.so/profile/integrations → New integration
2. Name: "MedFeed Sync" · Associated workspace: your workspace · Type: Internal
3. Copy the "Internal Integration Secret" → this is your `NOTION_TOKEN`

---

## Part 3: Render environment variables

Set these in Render dashboard → your cron service → Environment. The ones you
already set stay (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID). Add the new ones:

| Variable | Value | Source |
|---|---|---|
| `SUPABASE_URL` | `https://llrxhdgvfcfnajkhtlgc.supabase.co` | Existing |
| `SUPABASE_SERVICE_ROLE` | (service role key) | Supabase → Settings → API |
| `TELEGRAM_TOKEN` | (bot token) | Already set |
| `TELEGRAM_CHAT_ID` | (your chat ID) | Already set |
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` | console.anthropic.com |
| `LLM_MODEL` | `claude-sonnet-4-5-20250929` | Default |
| `LLM_DAILY_BUDGET` | `50` | Cap on articles/run |
| `PUBMED_API_KEY` | (existing) | NCBI account |
| `NOTION_TOKEN` | (from step above) | Notion integrations |
| `NOTION_DATABASE_ID` | `d2b8807f-8d79-42e0-9fc5-542b5723426b` | From Part 2 |
| `LOG_LEVEL` | `INFO` | |
| `DAYS_BACK` | `7` | |

**Remove** `LINE_CHANNEL_ACCESS_TOKEN` — no longer used (notifier code keeps it
as an optional legacy path, but the default pipeline skips it).

**Update** build command in Render to:
```
pip install --upgrade pip uv && uv pip install --system -e .
```
Or apply the new `render.yaml` by pushing it.

---

## Part 4: Deploy the code

### Option A — replace repo contents (cleanest)

```bash
cd /path/to/MedFeedJournalTracker
git checkout -b feat/v2-refactor
# Copy the contents of the v2 zip over, respecting .gitignore
# (delete old requirements.txt, test_scrapers.py if present)
git add -A
git commit -m "feat: v2 refactor — LLM + Telegram + Notion + CI"
git push -u origin feat/v2-refactor
# Open PR to main on GitHub; CI will run
```

### Option B — keep history side-by-side

Same, but merge into a `dev` branch first, verify one cron run works, then
promote to `main`.

### Local dev quickstart

```bash
cd MedFeedJournalTracker
cp .env.example .env.local
# Edit .env.local with real values
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate
pytest tests/         # Should be 46 passed
python main.py        # Full pipeline run against production Supabase
```

---

## Part 5: First run expectations

On the first production cron run after deploy:

1. **Fetcher:** picks up the newest articles from all 34 active journals (same as before).
2. **LLM:** processes up to 50 *previously unprocessed* articles. The first run will
   process 50 out of the existing backlog of ~1928 articles, not just new ones.
   This is intentional — the `llm_processed_at IS NULL` filter ensures we eventually
   catch up on the backlog over ~40 days at the default budget. To blitz the backlog
   faster, temporarily bump `LLM_DAILY_BUDGET` to 200 for a few days. Cost: $0.01/article
   × 1928 ≈ **$19 one-time** to fully backfill.
3. **Notion sync:** creates rows for every LLM-processed article from the last 2 days.
4. **Telegram:** sends the daily digest with tiered rendering (🔥 / 📖 / skipped).
5. **Cleanup:** keeps last 10,000 articles + 500 notifications.

---

## Part 6: Cost expectations

| Cost center | Estimate |
|---|---|
| Anthropic API (LLM summarize) | ~$0.01 × ~15 articles/day ≈ **$5/mo** |
| Supabase | Free tier sufficient (well under 500MB) |
| Render cron | Free plan |
| Telegram API | Free |
| Notion API | Free tier sufficient |

One-time backlog cost if you bump budget: ~$19.

### Daily-budget safety

The daily-budget cap is enforced **both** at the DB layer (via
`llm_processed_at IS NOT NULL` filter — already-processed articles are never
re-hit) and at the service layer (`daily_budget=50` cap per run). If the cron
somehow fires twice in one day, you'd process up to 100 articles total, not 50
× 2 on the same articles.

---

## Part 7: Rollback

If v2 misbehaves:

1. **Code:** revert the PR. Render auto-deploys the previous main.
2. **Schema:** `medfeed_backup_20260422/rollback.sql` drops the new columns,
   interests table, and RPC functions. Old v1 code will run cleanly against
   the reverted schema.

The rollback is fully safe: no existing article data is touched. The only loss
is LLM-generated summaries and relevance scores (they were added by the
migration and will be re-generated when v2 is re-deployed).

---

## Part 8: Future enhancements (parked)

These didn't make it into v2 but have clear hooks:

- **Telegram inline buttons** for "mark as read in Notion" without opening the app.
- **Per-journal override** of `days_back` (some journals publish rarely).
- **Relevance score explanation** — currently stored in LLM reasoning but not
  persisted. Add a `llm_reasoning` column if you want to debug bad scores.
- **Multi-user Telegram:** use the legacy `subscribers` table with `telegram_chat_id`
  column instead of the current single-chat model.
- **RLS:** all tables currently have RLS disabled. Fine for service-role-only access;
  enable when adding other auth paths.

---

## File layout reference

```
MedFeedJournalTracker/
├── .github/workflows/
│   ├── ci.yml                  # Lint + test on PR
│   ├── integration.yml         # Weekly live-API smoke test
│   └── manual-run.yml          # On-demand full-pipeline run
├── config/
│   ├── settings.py             # Typed Settings.from_env()
│   ├── journals.json           # [Legacy] now read from DB, kept as backup
│   └── ...
├── database/
│   └── supabase_client.py      # All DB ops (batch dedup, RPC cleanup)
├── llm/
│   └── summarizer.py           # Claude Sonnet + JSON output + retry
├── notifier/
│   ├── base_notifier.py        # Abstract base
│   ├── telegram_notifier.py    # Primary
│   └── formatter.py            # 3-tier relevance rendering
├── scrapers/                   # Unchanged from v1 (base class cleaned up)
│   ├── base_scraper.py
│   ├── pubmed_scraper.py
│   ├── rss_scraper.py
│   ├── elsevier_scraper.py
│   └── ieee_rss_scraper.py
├── services/
│   ├── fetcher_service.py      # Stage 1: fetch + batch dedup
│   ├── llm_service.py          # Stage 2: summarize + score (budget-capped)
│   ├── notifier_service.py     # Stage 3: digest + push
│   └── cleanup_service.py      # Stage 4: retention
├── sync/
│   └── notion_syncer.py        # Supabase → Notion append-only
├── tests/                      # 46 tests, all green
├── utils/
│   └── logger.py               # Unchanged
├── main.py                     # Thin orchestrator (~90 lines)
├── pyproject.toml              # uv + ruff + mypy + pytest config
├── render.yaml                 # Cron + env var template
├── .env.example
└── DEPLOYMENT.md               # ← you are here
```
