# MedFeed Journal Tracker

> Daily medical-literature tracker built around **dual push channels**:
> LINE for raw per-subscriber alerts, Telegram for an LLM-curated digest.
> Runs as a Render cron job at 06:00 Asia/Taipei.

---

## What it does

Every morning the tracker:

1. **Fetches** the past 7 days of papers across a curated set of colorectal-surgery and surgical-data-science journals (RSS + PubMed API + IEEE + Elsevier scrapers).
2. **De-duplicates** by DOI against a Supabase table of everything already seen.
3. **Blasts a raw LINE alert** to each subscribed collaborator — title, authors, journal, DOI link — filtered by their category (CRC / SDS). Independent of LLM; fires even if Claude is down.
4. **Scores + summarizes** each paper via Claude Sonnet 4.5 — a 3-sentence Chinese summary plus three 1–5 relevance scores (CRC / SDS / CV/DL), bounded by a daily budget.
5. **Mirrors** every LLM-processed paper into a Notion database as an append-only archive (optional).
6. **Sends a curated Telegram digest** to a single operator (me), tiered by peak score:
   - 🔥 **Must-read** (any score ≥ 4): full summary + link
   - 📖 **Worth a skim** (peak 2–3): title + scores only
   - 🚫 **Skipped** (all 1s): counted but not shown
7. **Prunes** old rows to keep the DB under its free-plan quota.

## Architecture

```
┌──────────────┐           ┌──────────────┐       ┌─────────────────────┐
│ PubMed / RSS │ ──Fetch─► │   Supabase   │ ──┬─► │ LINE push (many)    │
│  + scrapers  │           │  (Postgres)  │   │   │ raw · category only │
└──────────────┘           └──────┬───────┘   │   └─────────────────────┘
                                  │           │
                                  │           │   ┌─────────────────────┐
                                  ▼           │   │ Claude API          │
                           ┌──────────────┐   │   │ (summary + scoring) │
                           │  LLM stage   │ ──┼─► └─────────┬───────────┘
                           │ (budget 50)  │   │             ▼
                           └──────────────┘   │   ┌─────────────────────┐
                                              │   │ Notion archive      │
                                              │   └─────────────────────┘
                                              │   ┌─────────────────────┐
                                              └─► │ Telegram digest (1) │
                                                  │ tiered by relevance │
                                                  └─────────────────────┘
```

The two notifier paths are deliberately decoupled: LINE alerts go out at stage 1.5, so a Claude outage or an exhausted LLM budget never silences subscribers.

## Notification channels at a glance

| | **LINE** | **Telegram** |
|---|---|---|
| Audience | Multiple collaborators | Single operator (me) |
| Source | Supabase `subscribers` table, filtered by category | Fixed `TELEGRAM_CHAT_ID` |
| Content | Title + authors + journal + DOI link | Full Chinese summary + relevance tiers |
| Triggers on | Every new fetched article | LLM-processed articles from last 24 h |
| Runs if LLM fails | ✅ yes | ❌ skipped |

## Quick start (local dev)

```bash
cp .env.example .env.local        # Fill in real values
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate

pytest tests/                     # 60 tests, ~7 seconds
python main.py                    # One pipeline run
```

Edit `config/subscribers.json` (gitignored) to add/remove LINE recipients — the next `python main.py` upserts the list into Supabase automatically.

## Production (Render)

- Cron at 06:00 Asia/Taipei (`0 22 * * *` UTC) runs `python main.py`.
- Build uses `requirements.txt` (auto-generated from `pyproject.toml` via `scripts/sync_requirements.py`); Python pinned via `.python-version`.
- Subscribers are read from Supabase — no `subscribers.json` ever lives on the container.

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for env vars, rollback, and the full migration guide.

## Configuration

| Env var | Required | Purpose |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE` | ✅ | DB access |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | ✅ | Operator digest |
| `ANTHROPIC_API_KEY` | ✅ | LLM summary + scoring |
| `LINE_CHANNEL_ACCESS_TOKEN` | optional | Enables LINE alerts; subscribers come from DB |
| `NOTION_TOKEN` + `NOTION_DATABASE_ID` | optional | Enables Notion mirror |
| `PUBMED_API_KEY` | optional | Raises PubMed rate limit |
| `LLM_MODEL`, `LLM_DAILY_BUDGET`, `DAYS_BACK`, `LOG_LEVEL` | optional | All have sensible defaults |

## Tune LLM scoring without touching code

Open Supabase → `interests` table → edit the `description` field of any row (CRC / SDS / CVDL). The prompt picks up the change on the next cron run — no redeploy needed.

## Repository layout

```
main.py                      # Pipeline entry point
config/     settings.py      # Typed env loader (fail-fast on missing required)
            journals.json    # Seed list of tracked journals
scrapers/                    # BaseScraper + RSS / IEEE / Elsevier / PubMed
llm/                         # Claude client + prompt + parsing
services/                    # One class per pipeline stage (Fetcher, LLM,
                             # LineAlert, Notifier, Cleanup)
notifier/                    # LineNotifier, TelegramNotifier, formatter
sync/                        # Notion mirror
database/                    # Thin Supabase wrapper
tests/                       # 60 unit tests, no live-API calls
scripts/                     # Dev helpers (sync_requirements, …)
.github/workflows/           # CI (lint + type-check + test) on every push
```

## License

MIT — see `LICENSE`.
