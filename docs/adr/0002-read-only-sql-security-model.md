# 0002 — Query Agent 唯讀 SQL 安全模型

- 狀態：已採用
- 日期：2026-06
- 相關：ADR-0001

## 背景

Query Agent（ADR-0001）讓 LLM 產生 SQL 並對正式資料庫執行。LLM 產生的字串不可信任，必須防止：寫入 / DDL、疊加語句注入、時間型 DoS（`pg_sleep`）、檔案/網路函式、以及讀取 PII（`subscribers.line_user_id`）或系統表。

## 決策

所有 agent 查詢都經由單一 `SECURITY DEFINER` 的 RPC `execute_readonly_query(text)`（見 `database/migrations/2026_06_09_search_and_rpc_hardening.sql`），核心是**結構性防護**：

```sql
EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', query_text)
```

把使用者 SQL 包進子查詢——這在語法上就只允許「能當子查詢的 SELECT」，INSERT/UPDATE/DELETE/DDL/COPY 都會直接是語法錯誤。在此之上再加：

- 必須以 `select` 開頭。
- 禁止疊加語句（句中出現 `;`）——主要注入向量。
- 擋危險函式（`pg_sleep`、`pg_read_file`、`dblink`…）。
- 擋 PII / 系統表（`subscribers`、`notifications`、`pg_*`、`information_schema`、`auth.`）。
- `SET search_path = pg_catalog, public`、`statement_timeout = '5s'`、只 `GRANT` 給 `service_role`（移除 `anon`）。

## 後果

- ✅ 結構性防護（子查詢包裝）比關鍵字黑名單可靠得多。
- ✅ 過程中發現並修正一個潛在漏洞：**Postgres 正規表示式的單字邊界是 `\y` 不是 `\b`**（`\b` 是退格字元），舊版 `\b(insert|update|…)` 其實從未生效。改用 `\y` 後生效。
- ✅ 刻意**不**用 DDL 關鍵字黑名單去擋自由文字搜尋常見字（如 `drop`、`copy number`），避免誤殺——安全靠結構保證。
- ✅ 已對正式 DB 實測：正常查詢與含 `drop` 的搜尋可用；`subscribers`、疊加語句、`pg_sleep` 全被擋。
- ⚠️ 仍非「零信任」：未來若要更嚴，可改用只對特定表有 SELECT 權限的專用唯讀角色。

## 替代方案

- **純關鍵字黑名單**：脆弱，且 `\b` 陷阱證明易出錯。
- **專用唯讀 DB 角色 + 資料表層權限**：更強，但較重；目前的結構性防護已足夠，列為未來強化選項。
