# Journal Tracker

自動追蹤學術期刊最新文章，並根據類別推播到 Line Messaging API 的 Python 系統。

## 📖 目錄

- [系統簡介](#系統簡介)
- [功能特色](#功能特色)
- [技術架構](#技術架構)
- [快速開始](#快速開始)
- [詳細安裝](#詳細安裝)
- [使用說明](#使用說明)
- [新增訂閱者](#新增訂閱者)
- [新增期刊](#新增期刊)
- [設定自動排程](#設定自動排程)
- [常見問題](#常見問題)

---

## 系統簡介

Journal Tracker 是一個自動化系統，用於：

1. **追蹤多個學術期刊**的最新發表文章
2. **智慧去重**（基於 DOI）避免重複推播
3. **類別分類**（CRC / SDS）精準推播
4. **多訂閱者支援**，每個訂閱者可選擇感興趣的類別
5. **Line 推播**，每天自動通知最新文章

### 類別說明

- **CRC** (Colorectal Cancer)：大腸直腸癌相關期刊
- **SDS** (Surgical Data Science)：外科數據科學相關期刊

---

## 功能特色

### ✨ 核心功能

- 🔍 **自動抓取**：支援 13 個學術期刊的 RSS feeds
- 🏷️ **類別標籤**：CRC 和 SDS 兩大類別
- 👥 **多訂閱者**：支援多人訂閱，每人可選擇類別
- 🔄 **智慧去重**：基於 DOI，避免重複推播
- 💬 **Line 推播**：客製化訊息，只推播相關類別的文章
- 📦 **雲端資料庫**：使用 Supabase 儲存文章歷史
- ⏰ **自動排程**：每天自動執行

### 📊 目前追蹤的期刊

**SDS 類別（9 個期刊）**：
- IEEE Transactions on Medical Imaging
- Nature Machine Intelligence
- npj Digital Medicine
- Annual Review of Biomedical Data Science
- Journal of Biomedical Informatics
- IEEE Journal of Biomedical and Health Informatics
- IEEE Transactions on Medical Robotics and Bionics
- IEEE Transactions on Robotics
- IEEE Transactions on Automation Science and Engineering

**CRC 類別（4 個期刊）**：
- Diseases of the Colon and Rectum
- Colorectal Disease
- Techniques in Coloproctology
- International Journal of Colorectal Disease

詳細清單請參考 [JOURNAL_LIST.md](JOURNAL_LIST.md)

---

## 技術架構

### 系統組成

```
Journal Tracker 系統
├── 主系統（本地執行）
│   ├── 期刊爬蟲（RSS/網頁）
│   ├── Supabase 資料庫
│   ├── Line 推播服務
│   └── 自動排程（Cron/工作排程器）
│
└── Webhook 服務（雲端部署）
    ├── 收集 Line User IDs
    ├── 網頁介面管理
    └── 24/7 運行在 Render.com
```

### 技術棧

- **Python 3.9+**: 主要程式語言
- **Supabase (PostgreSQL)**: 雲端資料庫
- **Line Messaging API**: 推播通知
- **feedparser**: RSS 解析
- **BeautifulSoup4**: 網頁爬蟲
- **Flask**: Webhook 服務（雲端）
- **Render.com**: Webhook 服務部署平台

### 資料庫設計

- `journals` - 期刊資訊（含類別標籤）
- `subscribers` - 訂閱者資訊（含訂閱類別）
- `articles` - 文章記錄（DOI 去重）
- `notifications` - 推播記錄

---

## 快速開始

### 前置需求

- Python 3.9+
- pip
- Supabase 帳號（免費）
- Line Messaging API Channel
- Render.com 帳號（免費，用於 Webhook 服務）

### 5 分鐘快速設定

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 設定環境變數
# 將您的憑證填入 .env.local

# 3. 設定 Supabase 資料庫
# 在 Supabase SQL Editor 執行：
# - database/supabase_schema.sql
# - database/fix_subscribers_schema.sql

# 4. 執行程式
python main.py
```

---

## 詳細安裝

### 步驟 1: 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

**依賴套件**：
- python-dotenv
- supabase
- feedparser
- requests
- beautifulsoup4
- lxml

### 步驟 2: 設定 Supabase 資料庫

#### 2.1 建立 Supabase 專案

1. 前往 [Supabase](https://supabase.com)
2. 建立新專案
3. 記下 **Project URL** 和 **API Key**

#### 2.2 建立資料表

在 Supabase Dashboard → SQL Editor，依序執行：

**1. 建立基本 schema**：
```sql
-- 執行 database/supabase_schema.sql 的內容
```

**2. 修正訂閱者表（重要！）**：
```sql
-- 執行 database/fix_subscribers_schema.sql 的內容
-- 這允許同一個 Line 帳號訂閱多個類別
```

### 步驟 3: 設定 Line Messaging API

#### 3.1 建立 Line Channel

1. 前往 [Line Developers Console](https://developers.line.biz/console/)
2. 建立 Provider（如果沒有）
3. 建立 **Messaging API Channel**
4. 記下 **Channel Access Token**

#### 3.2 設定環境變數

建立 `.env.local` 檔案：

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=your_anon_key
# 或使用 service role key（權限更高）
SUPABASE_SERVICE_ROLE=your_service_role_key

# Line Messaging API
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token

# 其他設定
LOG_LEVEL=INFO
```

### 步驟 4: 設定期刊和訂閱者

#### 4.1 期刊設定

期刊設定已預設完成（13 個期刊），檔案位於：
- `config/journals.json`

如需新增期刊，請參考 [新增期刊](#新增期刊) 章節。

#### 4.2 訂閱者設定

需要取得訂閱者的 Line User ID，請參考 [新增訂閱者](#新增訂閱者) 章節。

### 步驟 5: 測試執行

```bash
# 執行主程式
python main.py
```

第一次執行會：
1. 同步期刊和訂閱者到 Supabase
2. 抓取最近 7 天的文章
3. 儲存新文章
4. 推播通知給訂閱者

---

## 使用說明

### 執行模式

#### 手動執行

```bash
python main.py
```

**適合**：
- 測試系統
- 臨時檢查新文章
- 調試問題

#### 自動排程執行

設定每天自動執行，請參考 [設定自動排程](#設定自動排程) 章節。

### 執行流程

```
1. 載入設定與環境變數
   ↓
2. 連接 Supabase 和 Line API
   ↓
3. 同步期刊與訂閱者資料
   ↓
4. 對每個期刊：
   ├── 抓取最近 7 天的文章
   ├── 檢查 DOI 是否已存在（去重）
   └── 儲存新文章（含類別標籤）
   ↓
5. 如果有新文章：
   ├── 按類別和期刊分組
   ├── 對每個訂閱者：
   │   ├── 篩選符合其訂閱類別的文章
   │   ├── 格式化訊息
   │   ├── 推播到 Line
   │   └── 記錄推播狀態
   ↓
6. 輸出執行報告
```

### 「新文章」的定義

文章被視為「新文章」需同時滿足兩個條件：

1. **時間條件**：發表日期在過去 **7 天內**
2. **去重條件**：DOI 不存在於資料庫中

**範例**：
```
Day 1: 抓到文章 A, B, C → 推播 A, B, C
Day 2: 抓到文章 A, B, C, D → 只推播 D（A,B,C 已存在）
Day 3: 抓到文章 A-D → 全部跳過（都已存在）
```

### 推播訊息格式

```
📚 黃士峯 的期刊更新 (2025/10/01)
類別：CRC
📅 顯示過去 7 天內的新文章

【Colorectal Disease】
1. Robotic repair of a traumatic recto‐vesical perforation...
   DOI: 10.1111/codi.17250
   作者: Smith J, Lee K
   🔗 https://onlinelibrary.wiley.com/...
   📅 2025-09-30

2. 另一篇文章標題...
   ...

【Techniques in Coloproctology】
1. 文章標題...
   ...

---
📊 共發現 6 篇新文章（過去 7 天）
```

---

## 新增訂閱者

### 概述

要讓新同事接收推播，需要：
1. 取得他的 **Line User ID**
2. 加入 `config/subscribers.json`
3. 執行同步

### 方法 1: 使用 Webhook 服務（推薦）⭐

#### 一次性設定（只需做一次）

**1. 部署 Webhook 服務到 Render.com**

```bash
cd webhook_app

# 上傳到 GitHub
git init
git add .
git commit -m "Line User ID webhook service"
git remote add origin https://github.com/您的帳號/line-user-id-service.git
git push -u origin main
```

在 Render.com：
1. 前往 https://render.com/
2. 用 GitHub 登入
3. New + → **Web Service**
4. 連接 `line-user-id-service` 儲存庫
5. 設定：
   - Runtime: **Python 3**
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
   - Plan: **Free**
6. 部署（等 2-5 分鐘）
7. 記下服務 URL（例如：`https://line-user-id-service.onrender.com`）

**2. 在 Line Developers Console 設定 Webhook**

1. 前往 https://developers.line.biz/console/
2. 選擇您的 Channel
3. Messaging API → Webhook settings
4. Webhook URL: `https://您的Render服務.onrender.com/webhook`
5. 點擊「Verify」（應顯示 Success）
6. 開啟「Use webhook」

**✅ 完成！之後就不用再設定了！**

#### 之後每次新增訂閱者

**超簡單流程**：

1. **讓同事加入 Line Official Account 好友**
2. **讓同事傳送訊息**（任意內容，例如："訂閱"）
3. **訪問網頁**：`https://您的Render服務.onrender.com/users`
4. **點擊「複製」按鈕**複製該同事的 User ID
5. **編輯** `config/subscribers.json`：

```json
{
  "subscribers": [
    // ... 現有訂閱者 ...
    {
      "name": "同事名字",
      "line_user_id": "貼上剛才複製的 User ID",
      "subscribed_category": "CRC"  // 或 "SDS"
    }
  ]
}
```

6. **執行同步**：
```bash
python main.py
```

**完成！** 同事會在下次有新文章時收到推播。

### 訂閱多個類別

如果同事想同時訂閱 CRC 和 SDS：

```json
{
  "subscribers": [
    {
      "name": "張醫師",
      "line_user_id": "U1234567890abcdef...",
      "subscribed_category": "CRC"
    },
    {
      "name": "張醫師",
      "line_user_id": "U1234567890abcdef...",  // 相同 User ID
      "subscribed_category": "SDS"
    }
  ]
}
```

張醫師會收到兩個類別的文章推播。

### 方法 2: 手動獲取（簡化版）

如果不想部署 Webhook 服務，可以臨時使用：

```bash
# 需要時才執行
pip install flask
python get_user_id.py

# 在另一個終端機
ngrok http 5000

# 在 Line Console 暫時設定 Webhook URL
# 讓同事傳訊息
# 複製 User ID
# 關閉服務
```

---

## 新增期刊

### 編輯 journals.json

在 `config/journals.json` 中新增：

```json
{
  "name": "期刊名稱",
  "issn": "1234-5678",
  "url": "https://journal-website.com",
  "rss_url": "https://journal-website.com/rss",
  "publisher_type": "springer",  // 或 "ieee", "nature", "wiley" 等
  "scraper_class": "RSSScraper",  // 或 "IEEERSSScraper"
  "category": "CRC"  // 或 "SDS"
}
```

### 驗證 RSS Feed

使用驗證工具測試新期刊的 RSS：

```bash
python verify_rss_feeds.py
```

### 同步到系統

```bash
python main.py
```

程式會自動同步新期刊到 Supabase。

### 選擇合適的爬蟲

- **RSSScraper**: 適用於大部分有 RSS feed 的期刊（Nature, Springer, Wiley 等）
- **IEEERSSScraper**: 專門用於 IEEE 期刊（有反爬蟲機制）
- **ElsevierScraper**: 用於 Elsevier/ScienceDirect 期刊（網頁爬蟲）

---

## 設定自動排程

### Windows 工作排程器

#### 方法 1: 使用圖形界面

1. 開啟「工作排程器」(Task Scheduler)
2. 建立基本工作
3. 設定：
   - **名稱**: Journal Tracker
   - **觸發程序**: 每天
   - **時間**: 早上 8:00
   - **動作**: 啟動程式
     - 程式: `C:\Users\...\Python\python.exe`
     - 引數: `C:\Users\...\journal_tracker\main.py`
     - 起始於: `C:\Users\...\journal_tracker`

#### 方法 2: 使用命令列

```powershell
# 查看設定指令
.\setup_cron.bat

# 或直接執行（替換路徑）
schtasks /create /tn "JournalTracker" /tr "python C:\Path\To\journal_tracker\main.py" /sc daily /st 08:00 /f
```

### Linux/Mac Cron

```bash
# 編輯 crontab
crontab -e

# 加入（每天早上 8:00 執行）
0 8 * * * cd /path/to/journal-tracker && /usr/bin/python3 main.py >> /path/to/journal-tracker/logs/cron.log 2>&1
```

---

## 常見問題

### Q: 為什麼建議每天執行，而不是每週？

**A**: 雖然抓取「過去 7 天」的文章，但每天執行的原因：

1. **避免遺漏**：文章可能延遲 2-3 天才加入 RSS feed
2. **DOI 去重**：自動避免重複推播，不用擔心
3. **即時性**：使用者每天收到最新文章，體驗更好
4. **錯誤恢復**：如果某天系統出錯，隔天還能補抓

**執行成本很低**：
- ⏱️ 執行時間：20-30 秒
- 💾 流量：很小（只下載 RSS）
- 🔋 資源：幾乎可忽略

### Q: 如何確認系統正常運作？

**A**: 檢查以下項目：

1. **查看日誌**：
   ```bash
   # Windows PowerShell
   Get-Content logs\journal_tracker_$(Get-Date -Format "yyyyMMdd").log
   ```

2. **檢查 Supabase**：
   - 進入 Table Editor
   - 查看 `articles` 表是否有新文章
   - 查看 `notifications` 表是否有推播記錄

3. **測試推播**：
   - 手動執行 `python main.py`
   - 確認 Line 收到訊息

### Q: RSS feed 突然失效怎麼辦？

**A**: 解決方案：

1. **使用驗證工具**：
   ```bash
   python verify_rss_feeds.py
   ```

2. **查看錯誤日誌**：
   ```bash
   cat logs/journal_tracker_YYYYMMDD.log
   ```

3. **更新 RSS URL**：
   - 訪問期刊官網找新的 RSS URL
   - 更新 `config/journals.json`
   - 重新執行 `python main.py`

4. **替代方案**：
   - 使用 PubMed RSS（適用於大部分期刊）
   - 建立專用網頁爬蟲

### Q: 可以停用某個期刊嗎？

**A**: 兩種方法：

**方法 1: 在 Supabase 中停用**（不需修改設定檔）
```sql
UPDATE journals 
SET is_active = false 
WHERE name = '期刊名稱';
```

**方法 2: 從設定檔刪除**
- 從 `config/journals.json` 移除該期刊
- 重新執行 `python main.py`

### Q: 訂閱者想取消訂閱怎麼辦？

**A**: 

**方法 1: 在 Supabase 中停用**
```sql
UPDATE subscribers 
SET is_active = false 
WHERE line_user_id = 'U...';
```

**方法 2: 從設定檔移除**
- 從 `config/subscribers.json` 刪除該訂閱者
- 重新執行 `python main.py`

### Q: Line 推播失敗怎麼辦？

**A**: 檢查項目：

1. **Channel Access Token 是否正確**
2. **使用者是否已加入好友**（如果封鎖或刪除好友會失敗）
3. **查看 notifications 表的錯誤訊息**
4. **檢查 Line API 配額**（免費版有限制）

### Q: 文章抓不到怎麼辦？

**A**: 可能原因：

1. **過去 7 天沒有新文章**（正常現象）
2. **RSS feed 被封鎖或失效**
   - 使用 `verify_rss_feeds.py` 檢查
3. **網站結構改變**（網頁爬蟲可能需要更新）
4. **DOI 提取失敗**（文章被跳過）

### Q: 可以調整抓取天數嗎？

**A**: 可以！編輯 `main.py`：

```python
# 找到第 190 行附近
articles = scraper.fetch_articles(
    url=journal['url'],
    rss_url=journal.get('rss_url'),
    days_back=7  # ← 改為其他天數（如 14 或 30）
)
```

**注意**：第一次改大天數時，會抓取大量歷史文章。

---

## 專案結構

```
journal_tracker/
├── config/                         # 設定檔
│   ├── journals.json              # 期刊設定（13 個期刊）
│   └── subscribers.json           # 訂閱者設定
│
├── database/                       # 資料庫模組
│   ├── supabase_client.py         # Supabase 客戶端
│   ├── supabase_schema.sql        # 資料庫 Schema
│   └── fix_subscribers_schema.sql # 訂閱者表修正 SQL
│
├── scrapers/                       # 爬蟲模組
│   ├── base_scraper.py            # 爬蟲基類
│   ├── rss_scraper.py             # 通用 RSS 爬蟲
│   ├── ieee_rss_scraper.py        # IEEE 專用爬蟲
│   └── elsevier_scraper.py        # Elsevier 爬蟲
│
├── notifier/                       # 通知模組
│   └── line_notifier.py           # Line 推播服務
│
├── utils/                          # 工具模組
│   └── logger.py                  # 日誌系統
│
├── webhook_app/                    # Webhook 服務（部署到雲端）
│   ├── app.py                     # Flask 應用
│   ├── requirements.txt           # Python 依賴
│   └── README.md                  # 部署說明
│
├── main.py                        # 主程式入口
├── requirements.txt               # Python 依賴
├── .env.local                     # 環境變數（不提交到 git）
├── .gitignore                     # Git 忽略檔案
│
├── README.md                      # 本文件
├── INSTALL.md                     # 詳細安裝指南
└── JOURNAL_LIST.md                # 期刊清單
```

---

## 維護與監控

### 查看日誌

日誌檔案位於 `logs/` 目錄：

```bash
# 查看今天的日誌
cat logs/journal_tracker_20251001.log

# Windows PowerShell
Get-Content logs\journal_tracker_$(Get-Date -Format "yyyyMMdd").log

# 即時監控（Linux/Mac）
tail -f logs/journal_tracker_$(date +%Y%m%d).log
```

### 監控 Supabase

在 Supabase Dashboard 可以：
- 查看 `articles` 表：確認文章是否被儲存
- 查看 `notifications` 表：確認推播記錄
- 檢查 `journals` 和 `subscribers` 表：確認設定同步

### Webhook 服務監控

訪問 Render Dashboard：
- 查看服務狀態（應為 "Live"）
- 查看部署日誌
- 查看服務運行日誌

---

## 效能與限制

### 系統效能

- **執行時間**: 20-30 秒（13 個期刊）
- **記憶體**: < 100 MB
- **網路流量**: < 5 MB/次
- **資料庫查詢**: 批量操作，高效

### Line API 限制

- **免費版**：
  - 推播次數：500 則/月
  - 如果訂閱者多，注意配額

### Render.com 限制（Webhook 服務）

- **免費版**：
  - 15 分鐘無活動會休眠
  - 首次訪問需等待 30 秒喚醒
  - 檔案系統不持久化（但不影響使用）

### Supabase 限制

- **免費版**：
  - 500 MB 資料庫空間（綽綽有餘）
  - 2 GB 頻寬/月
  - 7 天後專案會暫停（訪問一次即喚醒）

---

## 擴展與客製化

### 新增爬蟲

如果需要支援新的出版商：

1. 在 `scrapers/` 建立新檔案（如 `custom_scraper.py`）
2. 繼承 `BaseScraper` 並實作 `fetch_articles()`
3. 在 `main.py` 註冊新爬蟲

### 修改推播格式

編輯 `notifier/line_notifier.py` 的 `format_message()` 方法。

### 整合其他通訊平台

參考 `notifier/line_notifier.py` 的架構，建立：
- `telegram_notifier.py`
- `slack_notifier.py`
- `email_notifier.py`

### 新增類別

1. 在 `journals.json` 中為期刊設定新的 `category`
2. 在 `subscribers.json` 中使用新的 `subscribed_category`
3. 系統會自動處理新類別

---

## 故障排除

### 問題：推播沒有送出

**檢查**：
1. 訂閱者是否已同步到 Supabase
   ```bash
   # 在 Supabase SQL Editor
   SELECT * FROM subscribers WHERE is_active = true;
   ```

2. 文章類別是否符合訂閱者的類別
3. Line Channel Access Token 是否正確
4. 使用者是否已加入好友

### 問題：爬蟲抓不到文章

**檢查**：
1. RSS URL 是否有效
   ```bash
   python verify_rss_feeds.py
   ```

2. 過去 7 天是否真的有新文章（期刊可能更新頻率低）

3. DOI 提取是否成功（查看 debug 日誌）

### 問題：Webhook 服務收不到事件

**檢查**：
1. Render 服務是否在運行（Dashboard 顯示 "Live"）
2. Line Webhook URL 是否正確設定
3. Webhook 是否已啟用（"Use webhook" 開關）
4. 使用者是否真的傳送了訊息

---

## 安全性

### 環境變數

- ✅ 敏感資訊儲存在 `.env.local`
- ✅ `.gitignore` 排除環境變數檔案
- ⚠️ 絕對不要將 `.env.local` 提交到 Git

### Supabase 安全

建議啟用 Row Level Security (RLS)：

```sql
-- 在 Supabase SQL Editor 執行
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
```

### Line API 安全

- ✅ Channel Access Token 保密
- ✅ 定期檢查 API 使用情況
- ✅ 設定 IP 白名單（如果 Line 支援）

---

## 開發資訊

### 程式碼品質

- ✅ Type Hints（型別註解）
- ✅ Docstrings（完整的函式說明）
- ✅ 錯誤處理（try-except）
- ✅ 日誌記錄（logging）
- ✅ PEP 8 編碼規範

### 測試工具

- `test_scrapers.py` - 測試爬蟲功能
- `verify_rss_feeds.py` - 驗證所有 RSS feeds
- `get_user_id.py` - 本地 Webhook 測試工具

### 貢獻指南

如果您想擴展功能：

1. Fork 專案
2. 建立新分支
3. 實作功能
4. 測試
5. 提交 Pull Request

---

## 授權

MIT License

---

## 相關文件

- **[INSTALL.md](INSTALL.md)** - 詳細的安裝步驟和設定說明
- **[JOURNAL_LIST.md](JOURNAL_LIST.md)** - 完整的期刊清單
- **[webhook_app/README.md](webhook_app/README.md)** - Webhook 服務部署說明

---

## 支援

### 查看日誌

- 主程式日誌：`logs/journal_tracker_YYYYMMDD.log`
- Cron 日誌：`logs/cron.log`（如果使用 Cron）

### 檢查系統狀態

```bash
# 驗證 RSS feeds
python verify_rss_feeds.py

# 檢查資料庫連線
python -c "from database.supabase_client import SupabaseClient; import os; from dotenv import load_dotenv; load_dotenv('.env.local'); db = SupabaseClient(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_API_KEY')); print('✅ 資料庫連線成功')"
```

---

## 更新記錄

- **2025-10-01**: 
  - ✅ 新增 4 個 CRC 類別期刊
  - ✅ 修正訂閱者多類別支援
  - ✅ 部署 Webhook 服務到 Render.com
  - ✅ 完整系統測試通過

- **2025-09-30**: 
  - ✅ 建立 Journal Tracker 系統
  - ✅ 加入 9 個 SDS 期刊
  - ✅ 實作 Line 推播功能

---

**最後更新**: 2025-10-01  
**版本**: 1.0.0  
**狀態**: ✅ 生產就緒