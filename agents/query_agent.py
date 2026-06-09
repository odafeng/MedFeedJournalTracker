"""Natural language query agent — Text-to-SQL over Supabase.

Uses Claude tool_use in an agentic loop:
  User question -> Claude generates SQL -> execute via Supabase RPC -> Claude formats answer

Requires the `execute_readonly_query` RPC function in Supabase
(see database/setup_query_rpc.sql).
"""

from __future__ import annotations

import json
import logging
import os

from anthropic import Anthropic

logger = logging.getLogger("journal_tracker")

# Centralized model id. Override with QUERY_LLM_MODEL without touching code.
QUERY_MODEL = os.getenv("QUERY_LLM_MODEL", "claude-sonnet-4-6")

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
6. 【自由文字檢索很重要，務必照做】title 與 abstract 是英文，summary_zh 是繁體中文，
   使用者通常用中文提問，所以搜尋時一定要跨語言、跨欄位、拆關鍵字：
   (a) 先把使用者的概念同時想成「中文詞」和「對應的英文詞」。
       例如「手術影像分析」→ 中文：影像、手術、分割；英文：image, surgical, segmentation, vision。
   (b) 中文關鍵字去搜 summary_zh；英文關鍵字去搜 title 和 abstract。
   (c) 全部用 ILIKE '%單一詞%' 並用 OR 串起來，不要拿整串長片語比對
       （要 summary_zh ILIKE '%影像%' OR title ILIKE '%image%'，
        不要 title ILIKE '%手術影像分析%'，那樣幾乎一定是 0 筆）。
   (d) 若第一次查詢 0 筆，放寬關鍵字或換同義詞／上位詞再查一次，不要馬上回「找不到」。
   (e) 也可用 relevance_sds / relevance_crc / relevance_cvdl 的高分文章輔助召回。
7. 回答時引用具體數字和文章標題
8. 如果一次查詢不夠回答問題，可以多次查詢
9. 如果文章有 summary_zh，可以直接引用中文摘要
10. relevance_crc/sds/cvdl 欄位是 1-5 分的相關性評分
11. 列出文章時附上可點閱的連結，方便使用者直接打開原文：
    優先用 url 欄位；若 url 為空則用 https://doi.org/<doi>。SELECT 時記得一併取出 url 和 doi。
12. 這是多輪對話。若使用者用「那篇」「第二篇」「它的結論」等指代，請根據前面對話脈絡理解，
    必要時沿用上一輪查到的文章再追加查詢。

工具選擇：
- execute_sql：精確條件查詢（時間範圍、分數門檻、特定期刊、數量統計、列清單）用它。
- semantic_search（若有提供此工具）：概念性／主題式的模糊查詢優先用它
  （例如「跟手術影像分析相關的文章」「有沒有講腸道菌叢的」）。它用語意向量比對，
  不受用字與語言限制，通常比 ILIKE 更能命中。可先用 semantic_search 找到候選文章，
  再視需要用 execute_sql 補充細節（作者、分數、日期等）。

Formatting rules (IMPORTANT — output is displayed in LINE chat, NOT a browser):
- Do NOT use any Markdown syntax: no #, ##, **, *, ```, |, ---, > etc.
- Use plain text only
- Use numbered lists (1. 2. 3.) or bullet points (- or •) for structure
- Use blank lines to separate sections
- For emphasis, use【brackets】or《angle brackets》instead of **bold**
- Keep it concise and scannable on a phone screen
"""

SQL_TOOL = {
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
}

SEMANTIC_TOOL = {
    "name": "semantic_search",
    "description": (
        "Find articles by meaning (vector similarity) rather than keywords. "
        "Best for conceptual/topical questions where wording or language may not "
        "match the stored text. Returns the most similar articles as a JSON array "
        "with title, summary_zh, doi, url, journal_name and a similarity score."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The topic/concept to search for (any language).",
            },
            "match_count": {
                "type": "integer",
                "description": "How many articles to return (default 10).",
            },
        },
        "required": ["query"],
    },
}


class QueryAgent:
    """Agentic loop: user question -> Claude picks a tool -> execute -> format answer."""

    def __init__(self, anthropic_api_key: str, supabase_client, embedder=None) -> None:
        self.client = Anthropic(api_key=anthropic_api_key)
        self.db = supabase_client
        self.embedder = embedder
        self.max_turns = 5
        # Only expose semantic_search when embeddings are configured.
        self.tools = [SQL_TOOL] + ([SEMANTIC_TOOL] if embedder is not None else [])

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

    def _semantic_search(self, query: str, match_count: int = 10) -> str:
        """Embed the query and return the most similar articles via pgvector."""
        try:
            vector = self.embedder.embed(query)
            rows = self.db.match_articles(vector, match_count=match_count)
            result_str = json.dumps(rows, ensure_ascii=False, default=str)
            if len(result_str) > 8000:
                result_str = result_str[:8000] + "\n... (truncated)"
            return result_str
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _run_tool(self, name: str, tool_input: dict) -> str:
        if name == "execute_sql":
            sql = tool_input.get("sql", "")
            logger.info(f"[Agent] SQL: {tool_input.get('explanation') or sql[:80]}")
            return self._execute_sql(sql)
        if name == "semantic_search" and self.embedder is not None:
            query = tool_input.get("query", "")
            count = int(tool_input.get("match_count") or 10)
            logger.info(f"[Agent] semantic_search: {query[:80]}")
            return self._semantic_search(query, match_count=count)
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)

    def ask(self, question: str, history: list[dict] | None = None) -> str:
        """Run the agentic loop. Returns the final text answer.

        `history` is an optional list of prior {role, content} text turns (from
        earlier in the same LINE conversation) so the user can ask follow-ups
        like 「那第二篇呢?」. Only plain user/assistant text turns should be
        passed — not the intermediate tool_use/tool_result blocks.
        """
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": question})

        for turn in range(self.max_turns):
            response = self.client.messages.create(
                model=QUERY_MODEL,
                max_tokens=4096,
                # The system prompt + DB schema is large and static — cache it
                # so repeated turns/queries reuse it instead of re-billing input.
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=self.tools,
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
                    result = self._run_tool(block.name, block.input)
                    logger.info(f"[Agent] Result: {result[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        return "抱歉，查詢過程太長了，請嘗試更具體的問題。"
