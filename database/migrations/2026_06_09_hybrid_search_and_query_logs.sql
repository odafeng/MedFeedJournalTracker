-- Hybrid search + query analytics (2026-06-09)
--
-- 1. hybrid_search_articles: Reciprocal Rank Fusion (RRF) of vector similarity
--    and trigram keyword ranking. Gives better recall than either alone — the
--    keyword arm catches exact terms the embedding misses, the vector arm
--    catches paraphrases/cross-language. The agent's semantic_search tool calls
--    this when an embedder is configured.
-- 2. query_logs: one row per LINE query, so we can see what users actually ask,
--    which queries return nothing, latency and token cost — to tune prompts and
--    spot data gaps.

CREATE OR REPLACE FUNCTION hybrid_search_articles(
  query_text text,
  query_embedding vector(1536),
  match_count int DEFAULT 10,
  rrf_k int DEFAULT 50
)
RETURNS TABLE (
  id uuid,
  title text,
  summary_zh text,
  doi text,
  url text,
  category text,
  journal_name text,
  score float
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH semantic AS (
    SELECT a.id, row_number() OVER (ORDER BY a.embedding <=> query_embedding) AS rank
    FROM articles a
    WHERE a.embedding IS NOT NULL
    ORDER BY a.embedding <=> query_embedding
    LIMIT 40
  ),
  keyword AS (
    SELECT a.id,
           row_number() OVER (
             ORDER BY word_similarity(
               query_text,
               coalesce(a.title,'') || ' ' || coalesce(a.summary_zh,'') || ' ' || coalesce(a.abstract,'')
             ) DESC
           ) AS rank
    FROM articles a
    ORDER BY word_similarity(
      query_text,
      coalesce(a.title,'') || ' ' || coalesce(a.summary_zh,'') || ' ' || coalesce(a.abstract,'')
    ) DESC
    LIMIT 40
  ),
  fused AS (
    SELECT coalesce(s.id, k.id) AS id,
           coalesce(1.0 / (rrf_k + s.rank), 0.0)
         + coalesce(1.0 / (rrf_k + k.rank), 0.0) AS score
    FROM semantic s
    FULL OUTER JOIN keyword k ON s.id = k.id
  )
  SELECT a.id, a.title, a.summary_zh, a.doi, a.url, a.category,
         j.name AS journal_name, f.score
  FROM fused f
  JOIN articles a ON a.id = f.id
  JOIN journals j ON j.id = a.journal_id
  ORDER BY f.score DESC
  LIMIT match_count;
$$;

REVOKE EXECUTE ON FUNCTION hybrid_search_articles(text, vector, int, int) FROM anon;
GRANT EXECUTE ON FUNCTION hybrid_search_articles(text, vector, int, int) TO service_role;

CREATE TABLE IF NOT EXISTS query_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  line_user_id text,
  question text,
  tools_used text[],
  turns int,
  input_tokens int,
  output_tokens int,
  latency_ms int,
  answer_chars int,
  error text
);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs (created_at DESC);
