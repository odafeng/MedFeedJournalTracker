# 架構決策紀錄 (ADR)

本資料夾記錄 MedFeed 的重要架構決策。每份 ADR 描述一個決策的**背景、決定、後果與替代方案**，讓未來的人（包含未來的自己）理解「為什麼當初這樣做」。

格式採輕量版 [MADR](https://adr.github.io/madr/)。狀態：`提議中 / 已採用 / 已棄用 / 被取代`。

| 編號 | 標題 | 狀態 |
|---|---|---|
| [0001](0001-line-query-agent-text-to-sql.md) | LINE Query Agent：自然語言轉 SQL | 已採用 |
| [0002](0002-read-only-sql-security-model.md) | Query Agent 唯讀 SQL 安全模型 | 已採用 |
| [0003](0003-keep-query-agent-warm-on-render-free-tier.md) | 在 Render 免費方案上維持 Query Agent 喚醒 | 已採用 |
| [0004](0004-semantic-search-pgvector-openai.md) | 語意搜尋：pgvector + OpenAI embeddings | 已採用 |

新增 ADR 時複製既有檔案、遞增編號即可。決策若被推翻，不要刪除舊 ADR，改成「被取代」並連結到新的。
