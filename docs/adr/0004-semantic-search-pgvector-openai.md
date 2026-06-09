# 0004 — 語意搜尋：pgvector + OpenAI embeddings

- 狀態：已採用
- 日期：2026-06
- 相關：ADR-0001

## 背景

Query Agent 原本只靠 SQL `ILIKE '%關鍵字%'`（後加 `pg_trgm` GIN 索引）。問題：

- `title` / `abstract` 是英文，`summary_zh` 是中文，使用者多半用中文問 → 跨語言關鍵字常 0 筆。
- 關鍵字比對接不住「概念相近但用字不同」（例：問「手術影像分析」，但文章寫 "image-derived simulation"）。

雖然已用「跨語言、拆詞、跨欄位」的 prompt 緩解，但召回品質仍有上限。

## 決策

導入向量語意搜尋：

- **OpenAI `text-embedding-3-small`（1536 維）** 為每篇文章（title + summary_zh + abstract）建立向量；查詢時也即時嵌入問題。
- **pgvector**：`articles.embedding vector(1536)` 欄位 + **HNSW**（cosine）索引 + `match_articles(query_embedding, match_count)` RPC（`service_role` only）。見 `database/migrations/2026_06_09_pgvector_semantic_search.sql`。
- Query Agent 多一個 **`semantic_search` 工具**；agent 自行決定概念題用語意搜尋、精確條件用 SQL。
- 嵌入維護：每日 pipeline 一個 capped stage 嵌入新文章；既有文章用 `scripts/backfill_embeddings.py` 或「Backfill Embeddings」workflow 一次補齊。

**優雅降級**：未設 `OPENAI_API_KEY` 時不註冊 `semantic_search` 工具，自動退回 SQL/ILIKE，功能不受影響。

## 後果

- ✅ 概念 / 跨語言檢索大幅改善；已驗證語意鄰居合理（手術 + 影像/AI + 模擬 群聚）。
- ✅ 完全可選、可降級，不影響既有部署。
- ⚠️ 新增 OpenAI 相依與成本（`text-embedding-3-small` 極低，全庫約 $0.02）。
- ⚠️ 需維護 embedding（新文章嵌入 + 既有 backfill）；webhook 服務也需設 `OPENAI_API_KEY` 才會啟用。

## 替代方案

- **Postgres 全文檢索（tsvector）**：中文支援弱，仍是詞彙比對。
- **外部向量資料庫（Pinecone/Weaviate…）**：多一個服務與帳單；pgvector 直接長在既有 Supabase 上更簡單。
- **其他 embedding 供應商（Voyage 等）**：可行；選 OpenAI 是因使用者已有金鑰、生態成熟。
