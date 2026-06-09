# 0003 — 在 Render 免費方案上維持 Query Agent 喚醒

- 狀態：已採用
- 日期：2026-06
- 相關：ADR-0001

## 背景

Query Agent webhook 部署為 Render **免費** web service。免費方案閒置約 15 分鐘後會休眠，下次請求需冷啟動 **50 秒以上**。

實際症狀（由 Render log 確認）：使用者在 LINE 送出問題 → LINE 打 webhook → 服務正在冷啟動 → **LINE 的 webhook 逾時很短，等不到就放棄並丟棄請求** → 請求根本沒進到 Flask（無回覆、無 app log）。這比 reply token 過期更前面、在 HTTP 入口層就發生，程式內怎麼寫都救不到。

## 決策

用**保溫**避免休眠，而非改程式：

1. **GitHub Actions keep-alive**（`.github/workflows/keep-alive.yml`）：每 ~10 分鐘 ping `/health`。版控在 repo 內。
2. **外部 uptime 監測（UptimeRobot，5 分鐘）**：更可靠，作為雙保險。

兩者並存：請求進得來（保溫）→「搜尋中…」即時安撫 → 回答。

## 後果

- ✅ 免費維持喚醒，webhook 不再被冷啟動吃掉。
- ⚠️ GitHub 排程 workflow 在 repo 連續 60 天無 commit 後會被停用，且排程偶有延遲——故搭配 UptimeRobot 雙保險。
- ⚠️ 本質是免費方案上的權宜之計；若查詢量變大，考慮 ADR 替代方案。

## 替代方案

- **升級 Render 付費方案**：不休眠，但要錢。
- **搬到無冷啟動的平台**（Cloudflare Worker / Supabase Edge Function 當前置入口）：較大工程，現階段不需要。
- **靠 LINE webhook 重送**：不可靠，預設也未必開啟。
