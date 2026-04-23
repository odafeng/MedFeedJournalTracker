# MedFeed Journal Tracker v2

Automated tracking of 34 medical journals with LLM-powered relevance scoring and multi-channel output.

## What it does

Every morning at 06:00 Asia/Taipei:

1. Fetches the past 7 days of papers from 34 journals (PubMed API + RSS) spanning Colorectal Cancer, Surgical Data Science, and Computer Vision / Deep Learning.
2. De-duplicates by DOI against a Supabase store of all previously-seen papers.
3. Sends each new paper through Claude Sonnet 4.5 for a 3-sentence Chinese summary and three relevance scores (1–5) — CRC, SDS, CV/DL.
4. Pushes a tiered digest to Telegram:
   - 🔥 **Must-read** (any score ≥ 4): full summary + link
   - 📖 **Worth a skim** (peak 2–3): title + scores only
   - 🚫 **Skipped** (all 1s): counted but not shown
5. Mirrors every LLM-processed paper into a Notion database as an append-only archive.
6. Keeps DB bounded via Postgres RPC cleanup.

## Architecture

```
 ┌──────────────┐        ┌─────────────┐      ┌──────────────┐
 │ PubMed / RSS │  ───►  │  Supabase   │ ───► │  Telegram    │
 │  (34 sources)│        │  (Postgres) │      │  (push)      │
 └──────────────┘        └──────┬──────┘      └──────────────┘
                                │
                                ▼
                         ┌──────────────┐      ┌──────────────┐
                         │ Claude API   │ ───► │    Notion    │
                         │ (summary +   │      │   (archive)  │
                         │  scoring)    │      └──────────────┘
                         └──────────────┘
```

## Quick start

```bash
cp .env.example .env.local    # Fill in real values
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate

pytest tests/                 # 46 tests, ~3 seconds
python main.py                # One pipeline run
```

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — migration guide, env vars, IDs, rollback.
- **Notion database:** https://www.notion.so/d2b8807f8d7942e09fc5542b5723426b
- **Supabase project:** MedFeed (`llrxhdgvfcfnajkhtlgc`)

## Tune LLM scoring without touching code

Open Supabase → MedFeed → `interests` table → edit the `description` field of any row (CRC / SDS / CVDL). The change is picked up on the next cron run.

## License

MIT
