-- Semantic search via pgvector (2026-06-09)
--
-- Adds an embedding column + HNSW index + a similarity-search RPC so the LINE
-- query agent can do meaning-based retrieval (robust to wording/language)
-- instead of only keyword ILIKE. Embeddings are produced by OpenAI
-- text-embedding-3-small (1536 dims) — see services/embedding_service.py and
-- scripts/backfill_embeddings.py. Populating embeddings is a separate step;
-- match_articles only returns rows that already have one, so the feature
-- degrades gracefully before the backfill runs.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS idx_articles_embedding_hnsw
  ON articles USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION match_articles(
  query_embedding vector(1536),
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id uuid,
  title text,
  summary_zh text,
  doi text,
  url text,
  category text,
  journal_name text,
  similarity float
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT a.id, a.title, a.summary_zh, a.doi, a.url, a.category,
         j.name AS journal_name,
         1 - (a.embedding <=> query_embedding) AS similarity
  FROM articles a
  JOIN journals j ON j.id = a.journal_id
  WHERE a.embedding IS NOT NULL
  ORDER BY a.embedding <=> query_embedding
  LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION match_articles(vector, int) FROM anon;
GRANT EXECUTE ON FUNCTION match_articles(vector, int) TO service_role;
