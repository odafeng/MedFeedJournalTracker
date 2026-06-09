# 0001 — LINE Query Agent：自然語言轉 SQL

- 狀態：已採用
- 日期：2026-06

## 背景

每日 pipeline 會把文章、中文摘要、相關性分數寫進 Supabase（Postgres）。協作者想在 LINE 上用自然語言臨時查資料（「最近有哪些 CRC 高分論文？」「有沒有跟手術影像分析相關的？」），而不是只能被動接收每日推播。

限制：
- 查詢樣態無法預先窮舉，硬寫死的指令選單會很死板。
- 部署在 Render 免費方案，資源有限。
- 回覆顯示在 LINE 聊天室（純文字，不渲染 Markdown）。

## 決策

實作一個獨立的 **Query Agent**（`agents/query_agent.py`），用 Claude 的 tool_use 跑 agentic loop：

1. 使用者問題 → Claude 產生 SQL（或選用 `semantic_search`，見 ADR-0004）。
2. 透過 Supabase 唯讀 RPC 執行（見 ADR-0002）。
3. Claude 把結果整理成純文字回覆。

部署為獨立的 Render Web Service (`medfeed-query-agent`)，與每日 cron 解耦。Webhook（`agents/webhook.py`）採 **LINE Push API + 背景執行緒**而非 Reply API：agent 需 5–15 秒，Reply token 約 30 秒過期，疊加冷啟動風險太高；先回 200、背景處理完再 push。收到訊息時立即回「搜尋中…」讓使用者知道已收到。

## 後果

- ✅ 不需預先定義查詢；新問法不用改 code。
- ✅ 與每日 pipeline 完全解耦，互不影響。
- ⚠️ 每次查詢有 LLM 成本與延遲（已用 prompt caching 降低 input 成本）。
- ⚠️ Agent 產生任意 SQL 有安全風險 → 由 ADR-0002 處理。
- ⚠️ 免費 web service 會冷啟動 → 由 ADR-0003 處理。

## 替代方案

- **固定指令選單**：可預期但死板，無法涵蓋自由文字查詢。
- **外部 BI / 儀表板**：對單一 LINE 聊天介面而言過重。
- **直接讓 LLM 連 DB（無 RPC 包裝）**：安全面不可接受。
