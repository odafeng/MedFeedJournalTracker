"""Natural language query agent — Text-to-SQL over Supabase.

Uses Claude tool_use in an agentic loop:
  User question -> Claude generates SQL -> execute via Supabase RPC -> Claude formats answer

Requires the `execute_readonly_query` RPC function in Supabase
(see database/setup_query_rpc.sql).
"""

from __future__ import annotations

import json
import logging

from anthropic import Anthropic

logger = logging.getLogger("journal_tracker")

SONNET = "claude-sonnet-4-6"

DB_SCHEMA = """
Tables in the database:

1. journals
   - id: UUID PK
   - name: TEXT (journal name)
   - issn: TEXT
   - url, rss_url: TEXT
   - publisher_type: TEXT ('ieee', 'nature', 'elsevier', 'springer', 'wiley', 'pubmed', ...)
   - scraper_class: TEXT
   - category: TEXT ('CRC' or 'SDS')
   - is_active: BOOLEAN

2. articles (main table, ~3000 rows)
   - id: UUID PK
   - journal_id: UUID FK -> journals
   - title: TEXT (English title)
   - doi: TEXT UNIQUE
   - url: TEXT
   - published_date: DATE
   - authors: TEXT
   - abstract: TEXT (English abstract)
   - category: TEXT ('CRC' or 'SDS')
   - summary_zh: TEXT (Traditional Chinese summary from LLM, nullable)
   - relevance_crc: INT (1-5 relevance score, nullable)
   - relevance_sds: INT (1-5 relevance score, nullable)
   - relevance_cvdl: INT (1-5 relevance score, nullable)
   - llm_processed_at: TIMESTAMPTZ (nullable)
   - llm_model: TEXT (nullable)
   - discovered_at: TIMESTAMPTZ
   - created_at: TIMESTAMPTZ

3. subscribers
   - id: UUID PK
   - name: TEXT
   - line_user_id: TEXT UNIQUE
   - subscribed_category: TEXT ('CRC' or 'SDS')
   - is_active: BOOLEAN

4. interests (scoring categories)
   - id: UUID PK
   - code: TEXT ('CRC', 'SDS', 'CVDL')
   - name: TEXT
   - description: TEXT (detailed description)
   - is_active: BOOLEAN

5. notifications (alert audit log)
   - id: UUID PK
   - article_id: UUID FK -> articles
   - subscriber_id: UUID FK -> subscribers
   - sent_at: TIMESTAMPTZ
   - status: TEXT ('success' or 'failed')
   - error_message: TEXT

Common joins:
  articles JOIN journals ON articles.journal_id = journals.id
"""

SYSTEM_PROMPT = f"""你是一個醫學期刊資料庫助理。使用者會用自然語言提問，你需要查詢 PostgreSQL 資料庫來回答。

{DB_SCHEMA}

Rules:
1. 用繁體中文回答
2. 只能產生 SELECT 查詢（read-only）
3. 查詢結果太多時用 LIMIT 限制（預設 20）
4. 善用 JOIN 來取得期刊名稱
5. 日期欄位用 discovered_at 做時間篩選
6. 搜尋文章標題/摘要時用 ILIKE '%keyword%'
7. 回答時引用具體數字和文章標題
8. 如果一次查詢不夠回答問題，可以多次查詢
9. 如果文章有 summary_zh，可以直接引用中文摘要
10. relevance_crc/sds/cvdl 欄位是 1-5 分的相關性評分

Formatting rules (IMPORTANT — output is displayed in LINE chat, NOT a browser):
- Do NOT use any Markdown syntax: no #, ##, **, *, ```, |, ---, > etc.
- Use plain text only
- Use numbered lists (1. 2. 3.) or bullet points (- or •) for structure
- Use blank lines to separate sections
- For emphasis, use【brackets】or《angle brackets》instead of **bold**
- Keep it concise and scannable on a phone screen
"""

TOOLS = [
    {
        "name": "execute_sql",
        "description": (
            "Execute a read-only SQL query against the journal tracker database. "
            "Only SELECT statements are allowed. Returns results as a JSON array."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SELECT SQL query to execute",
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what this query does",
                },
            },
            "required": ["sql"],
        },
    },
]


class QueryAgent:
    """Agentic loop: user question -> Claude generates SQL -> execute -> format answer."""

    def __init__(self, anthropic_api_key: str, supabase_client) -> None:
        self.client = Anthropic(api_key=anthropic_api_key)
        self.db = supabase_client
        self.max_turns = 5

    def _execute_sql(self, sql: str) -> str:
        """Execute read-only SQL via Supabase RPC function."""
        try:
            response = self.db.client.rpc(
                "execute_readonly_query",
                {"query_text": sql},
            ).execute()
            result_str = json.dumps(response.data, ensure_ascii=False, default=str)
            if len(result_str) > 8000:
                result_str = result_str[:8000] + "\n... (truncated)"
            return result_str
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def ask(self, question: str) -> str:
        """Run the agentic loop. Returns the final text answer."""
        messages = [{"role": "user", "content": question}]

        for turn in range(self.max_turns):
            response = self.client.messages.create(
                model=SONNET,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return "".join(
                    b.text for b in response.content if b.type == "text"
                )

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    sql = block.input.get("sql", "")
                    explanation = block.input.get("explanation", "")
                    logger.info(f"[Agent] SQL: {explanation or sql[:80]}")

                    result = self._execute_sql(sql)
                    logger.info(f"[Agent] Result: {result[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        return "抱歉，查詢過程太長了，請嘗試更具體的問題。"
