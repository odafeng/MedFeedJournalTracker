-- Read-only query function for the AI agent.
-- Already applied to production Supabase (2026-06-06).
-- Kept here for reference / re-deployment.

DROP FUNCTION IF EXISTS execute_readonly_query(text);

CREATE OR REPLACE FUNCTION execute_readonly_query(query_text text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET statement_timeout = '5s'
AS $$
DECLARE
  result jsonb;
  normalized text;
BEGIN
  normalized := lower(trim(query_text));

  IF NOT (normalized LIKE 'select%') THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  IF normalized ~* '\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|execute)\b' THEN
    RAISE EXCEPTION 'Write/DDL operations are not allowed';
  END IF;

  EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', query_text)
    INTO result;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

GRANT EXECUTE ON FUNCTION execute_readonly_query(text) TO anon;
GRANT EXECUTE ON FUNCTION execute_readonly_query(text) TO service_role;
