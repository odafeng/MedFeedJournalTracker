-- Search performance + read-only RPC hardening (2026-06-09)
--
-- Part 1: pg_trgm GIN indexes so the query agent's ILIKE '%kw%' free-text
--         search is fast and fuzzy instead of a full table scan.
-- Part 2: harden execute_readonly_query.
--
-- IMPORTANT lesson baked in here: Postgres regex uses \y for a word boundary,
-- NOT \b (which is a backspace character). The previous version's
-- \b(insert|update|...) write-protection therefore never matched anything —
-- it only "worked" because the query is executed as a subquery in
-- `FROM (%s) t`, which by itself makes any non-SELECT statement a syntax error.
-- We lean on that structural guarantee and drop the keyword blocklist (it also
-- caused false positives on legit free-text searches like 'drop' or
-- 'copy number variation'), keeping only the checks that actually matter for a
-- single SELECT expression: no stacked statements, no dangerous functions, no
-- PII/system tables. Plus: pinned search_path and no anon grant.

-- ---- Part 1: trigram indexes ------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_articles_title_trgm
  ON articles USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_abstract_trgm
  ON articles USING gin (abstract gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_summary_zh_trgm
  ON articles USING gin (summary_zh gin_trgm_ops);

-- ---- Part 2: hardened read-only RPC ----------------------------------------
CREATE OR REPLACE FUNCTION execute_readonly_query(query_text text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET statement_timeout = '5s'
SET search_path = pg_catalog, public
AS $$
DECLARE
  result jsonb;
  normalized text;
  trimmed text;
BEGIN
  normalized := lower(trim(query_text));
  trimmed := rtrim(normalized, ';');

  IF NOT (normalized LIKE 'select%') THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  -- Reject stacked statements (the primary injection vector). A single
  -- trailing semicolon is fine.
  IF position(';' in trimmed) > 0 THEN
    RAISE EXCEPTION 'Multiple statements are not allowed';
  END IF;

  -- Dangerous functions usable inside a SELECT (time-based DoS / file / network).
  -- Plain DML/DDL/COPY are already impossible because the query is executed as
  -- a subquery in `FROM (%s) t`, where only a valid SELECT expression parses.
  IF normalized ~* '(pg_sleep|pg_read_file|pg_ls_dir|lo_import|lo_export|dblink|pg_terminate_backend|pg_cancel_backend)' THEN
    RAISE EXCEPTION 'Disallowed function call';
  END IF;

  -- PII / system catalogs. Postgres uses \y for word boundary (\b is backspace).
  IF normalized ~* '\y(subscribers|notifications)\y'
     OR normalized ~* '\yinformation_schema\y'
     OR normalized ~* '\ypg_[a-z]'
     OR normalized ~* '\yauth\.' THEN
    RAISE EXCEPTION 'Access to that table is not allowed';
  END IF;

  EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', query_text)
    INTO result;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- Webhook authenticates with the service_role key; anon should not be able to
-- run arbitrary SELECTs.
REVOKE EXECUTE ON FUNCTION execute_readonly_query(text) FROM anon;
GRANT EXECUTE ON FUNCTION execute_readonly_query(text) TO service_role;
