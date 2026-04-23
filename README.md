# MedFeed Journal Tracker

> 每日醫學文獻追蹤系統,採用**雙通道推播**設計:
> LINE 推播給多位訂閱者、Telegram 推播給單一使用者的 LLM 精選 digest。
> 部署在 Render,每日上午 06:00(台北時間)透過 cron 自動執行。

---

## 這個系統在做什麼

每天早上系統會:

1. **抓取**一組精選的大腸直腸外科(CRC)與外科資料科學(SDS)期刊,過去 7 天的新文章 — 透過 RSS、PubMed API、IEEE 和 Elsevier 爬蟲混合抓取。
2. **DOI 去重**,與 Supabase 中所有看過的文章比對,已看過的直接跳過。
3. **推送 LINE 原始快訊**給每位訂閱的協作者 — 包含標題、作者、期刊、DOI 連結 — 依訂閱類別(CRC / SDS)過濾。這一步**不依賴 LLM**,Claude 掛掉也照推。
4. **LLM 摘要與評分** — 透過 Claude Sonnet 4.5,為每篇論文產出 3 句中文摘要,以及三個 1–5 的相關性分數(CRC、SDS、CV/DL),受每日預算上限保護。
5. **同步到 Notion**,把所有經 LLM 處理過的論文鏡射到 Notion database,當作永久檔案庫(選用)。
6. **推送 Telegram 精選 digest** 給單一操作者(我本人),依最高分數分層顯示:
   - 🔥 **必讀**(任一分數 ≥ 4):完整摘要 + 連結
   - 📖 **可略讀**(峰值 2–3):只顯示標題 + 分數
   - 🚫 **跳過**(全 1):只計數、不展開
7. **清理舊資料**,把 DB 控制在免費方案額度內。

## 系統架構

```
┌──────────────┐           ┌──────────────┐       ┌─────────────────────┐
│ PubMed / RSS │ ──抓取──► │   Supabase   │ ──┬─► │ LINE 推播(多人)    │
│  + 各爬蟲    │           │  (Postgres)  │   │   │ 原始快訊 · 按類別   │
└──────────────┘           └──────┬───────┘   │   └─────────────────────┘
                                  │           │
                                  │           │   ┌─────────────────────┐
                                  ▼           │   │ Claude API          │
                           ┌──────────────┐   │   │(摘要 + 評分)       │
                           │  LLM 階段    │ ──┼─► └─────────┬───────────┘
                           │(預算 50 篇)│   │             ▼
                           └──────────────┘   │   ┌─────────────────────┐
                                              │   │ Notion 檔案庫       │
                                              │   └─────────────────────┘
                                              │   ┌─────────────────────┐
                                              └─► │ Telegram digest(1人)│
                                                  │ 依相關性分層顯示    │
                                                  └─────────────────────┘
```

兩條推播路徑**刻意解耦** — LINE 快訊在 Stage 1.5 執行,所以 Claude 掛掉或 LLM 預算爆掉時,訂閱者不會被靜默。

## 兩個通道的分工

| | **LINE** | **Telegram** |
|---|---|---|
| 對象 | 多位協作者 | 單一操作者(我) |
| 訂閱者來源 | Supabase `subscribers` 資料表,按類別過濾 | 固定 `TELEGRAM_CHAT_ID` |
| 訊息內容 | 標題 + 作者 + 期刊 + DOI 連結 | 完整中文摘要 + 相關性分層 |
| 觸發來源 | 每次抓到的新文章 | 過去 24 小時已 LLM 處理的文章 |
| LLM 掛掉還會推嗎 | ✅ 會 | ❌ 不會 |

## 本機開發快速上手

```bash
cp .env.example .env.local        # 填入真實的環境變數值
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate

pytest tests/                     # 60 個測試,約 7 秒
python main.py                    # 跑一次完整 pipeline
```

編輯 `config/subscribers.json`(gitignored)就能新增或移除 LINE 訂閱者 — 下次執行 `python main.py` 時會自動 upsert 到 Supabase。

## 正式環境(Render)

- 每日 06:00 台北時間(UTC `0 22 * * *`)觸發 cron job,執行 `python main.py`。
- Build 使用 `requirements.txt`(從 `pyproject.toml` 透過 `scripts/sync_requirements.py` 自動產生);Python 版本透過 `.python-version` 固定。
- 訂閱者從 Supabase 讀取 — 容器內**不會**有 `subscribers.json`。

詳細部署步驟、環境變數清單、rollback 方式,請見 **[DEPLOYMENT.md](DEPLOYMENT.md)**。

## 環境變數

| 變數 | 必填 | 用途 |
|---|---|---|
| `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE` | ✅ | DB 連線 |
| `TELEGRAM_TOKEN`、`TELEGRAM_CHAT_ID` | ✅ | Telegram 操作者 digest |
| `ANTHROPIC_API_KEY` | ✅ | LLM 摘要與評分 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 選填 | 啟用 LINE 快訊;訂閱者來源是 DB |
| `NOTION_TOKEN` + `NOTION_DATABASE_ID` | 選填 | 啟用 Notion 鏡射 |
| `PUBMED_API_KEY` | 選填 | 提高 PubMed rate limit |
| `LLM_MODEL`、`LLM_DAILY_BUDGET`、`DAYS_BACK`、`LOG_LEVEL` | 選填 | 皆有預設值 |

## 不改 code 也能調整 LLM 評分

到 Supabase → `interests` 資料表 → 編輯任一列(CRC / SDS / CVDL)的 `description` 欄位。下次 cron 執行時會直接套用新的 prompt,不用 redeploy。

## 容錯設計

每個 pipeline stage 都用獨立的 `try/except` 包著,任何一個 stage 失敗都不會把後面的靜音。例如:

- **LLM 掛了** → LINE 已經推完,Telegram 會嘗試送出當天可用的精選(可能為空 digest),cleanup 照跑。
- **Telegram 掛了** → LINE 已經推完,Notion 已同步,cleanup 照跑。
- **任一 stage 失敗** → exit code 1,Render dashboard 會標紅,但過程已盡力跑完。
- **全部 stage 成功** → exit code 0。

## 專案結構

```
main.py                      # Pipeline 進入點
config/     settings.py      # 型別化 env 載入器(啟動時 fail-fast)
            journals.json    # 追蹤的期刊清單
scrapers/                    # BaseScraper + RSS / IEEE / Elsevier / PubMed
llm/                         # Claude 客戶端 + prompt + 結果解析
services/                    # 每個 pipeline stage 一個 class
                             # (Fetcher, LLM, LineAlert, Notifier, Cleanup)
notifier/                    # LineNotifier, TelegramNotifier, formatter
sync/                        # Notion 鏡射
database/                    # Supabase 封裝
tests/                       # 60 個單元測試,不呼叫任何外部 API
scripts/                     # 開發用小工具(sync_requirements …)
.github/workflows/           # CI(lint + 型別檢查 + 測試),每次 push 觸發
```

## License

MIT — 詳見 `LICENSE`。
