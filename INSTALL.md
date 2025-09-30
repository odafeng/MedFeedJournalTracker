# Journal Tracker 安裝指南

## 系統需求

- Python 3.9 或更高版本
- pip（Python 套件管理器）
- Supabase 帳號
- Line Messaging API Channel

## 安裝步驟

### 1. 克隆或下載專案

```bash
cd /path/to/your/workspace
# 如果已經在專案目錄中，跳過此步驟
```

### 2. 安裝 Python 依賴套件

```bash
pip install -r requirements.txt
```

如果您使用虛擬環境（建議）：

```bash
# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 3. 設定 Supabase 資料庫

#### 3.1 建立 Supabase 專案

1. 前往 [Supabase](https://supabase.com)
2. 登入或註冊帳號
3. 建立新專案
4. 記下專案的 URL 和 API Key

#### 3.2 建立資料表

1. 在 Supabase Dashboard 中，進入 SQL Editor
2. 開啟專案中的 `database/supabase_schema.sql` 檔案
3. 複製整個 SQL 內容
4. 貼到 Supabase SQL Editor 中
5. 執行（點擊 Run 或按 Ctrl+Enter）

這會建立以下資料表：
- `journals` - 期刊資訊
- `subscribers` - 訂閱者資訊
- `articles` - 文章記錄
- `notifications` - 推播記錄

### 4. 設定 Line Messaging API

#### 4.1 建立 Line Channel

1. 前往 [Line Developers Console](https://developers.line.biz/)
2. 登入或註冊 Line 開發者帳號
3. 建立 Provider（如果還沒有）
4. 建立 Messaging API Channel
5. 在 Channel 設定中：
   - 啟用 "Use webhooks"（如果需要回應訊息）
   - 在 "Messaging API" 頁籤取得 Channel Access Token

#### 4.2 取得使用者 ID

推播訊息需要使用者的 Line User ID。取得方式：

**方法 1: 使用官方工具**
- 邀請使用者加入您的 Line Official Account 好友
- 使用 Line Messaging API 的 Profile API 取得 User ID

**方法 2: 使用測試工具**
- 使用 Line 官方的 [Messaging API Simulator](https://developers.line.biz/console/)

**方法 3: 從 Webhook 取得**
- 當使用者發送訊息給您的 Bot 時，webhook 會包含 User ID

### 5. 設定環境變數

複製 `.env.example` 為 `.env` 或 `.env.local`：

```bash
cp .env.example .env.local
```

編輯 `.env.local`，填入您的憑證：

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=your_anon_key_here
# 或使用 service role key (更高權限)
SUPABASE_SERVICE_ROLE=your_service_role_key_here

# Line Messaging API
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here

# 其他設定
LOG_LEVEL=INFO
```

⚠️ **重要**: 
- `SUPABASE_API_KEY` 是 anon key（公開金鑰）
- `SUPABASE_SERVICE_ROLE` 是 service role key（私密金鑰，權限更高）
- 程式會優先使用 `SUPABASE_SERVICE_ROLE`，如果沒有則使用 `SUPABASE_API_KEY`
- 絕對不要將 `.env.local` 提交到版本控制系統！

### 6. 設定期刊和訂閱者

#### 6.1 設定期刊 (`config/journals.json`)

已預設包含 9 個期刊，全部屬於 SDS 類別。

如需新增 CRC 類別的期刊，編輯 `config/journals.json`：

```json
{
  "journals": [
    {
      "name": "期刊名稱",
      "issn": "1234-5678",
      "url": "https://journal-website.com",
      "rss_url": "https://journal-website.com/rss",
      "publisher_type": "ieee",
      "scraper_class": "RSSScraper",
      "category": "CRC"  // 改為 CRC
    }
  ]
}
```

#### 6.2 設定訂閱者 (`config/subscribers.json`)

將範例訂閱者替換為真實的使用者資訊：

```json
{
  "subscribers": [
    {
      "name": "張醫師",
      "line_user_id": "實際的 Line User ID",
      "subscribed_category": "CRC"
    },
    {
      "name": "王研究員",
      "line_user_id": "實際的 Line User ID",
      "subscribed_category": "SDS"
    }
  ]
}
```

### 7. 測試執行

#### 7.1 測試爬蟲功能

```bash
python test_scrapers.py
```

這會測試 RSS 和 Elsevier 爬蟲是否正常運作。

#### 7.2 執行主程式

```bash
python main.py
```

第一次執行時，程式會：
1. 同步期刊和訂閱者資料到 Supabase
2. 抓取最近 7 天的文章
3. 儲存新文章到資料庫
4. 推播通知給訂閱者

### 8. 設定自動排程

#### 8.1 Linux/Mac (使用 Cron)

```bash
# 賦予執行權限
chmod +x setup_cron.sh

# 執行設定腳本
./setup_cron.sh
```

或手動編輯 crontab：

```bash
crontab -e
```

加入以下行（每天早上 8:00 執行）：

```bash
0 8 * * * cd /path/to/journal-tracker && /usr/bin/python3 main.py >> /path/to/journal-tracker/logs/cron.log 2>&1
```

#### 8.2 Windows (使用工作排程器)

**方法 1: 使用腳本**

執行 `setup_cron.bat` 查看設定指令。

**方法 2: 手動設定**

1. 開啟「工作排程器」(Task Scheduler)
2. 建立基本工作
3. 設定：
   - 名稱: Journal Tracker
   - 觸發程序: 每天，早上 8:00
   - 動作: 啟動程式
   - 程式: `C:\Path\To\Python\python.exe`
   - 引數: `C:\Path\To\journal-tracker\main.py`
   - 起始於: `C:\Path\To\journal-tracker`

## 驗證安裝

檢查以下項目：

- [ ] Python 依賴套件已安裝
- [ ] Supabase 資料表已建立
- [ ] 環境變數已設定
- [ ] 期刊設定檔已更新
- [ ] 訂閱者設定檔已更新（包含真實的 Line User ID）
- [ ] 測試爬蟲成功
- [ ] 主程式執行成功
- [ ] 收到 Line 推播訊息
- [ ] Cron job 或工作排程器已設定

## 常見問題

### Q: 無法連接 Supabase

**A:** 檢查：
- Supabase URL 是否正確
- API Key 是否正確
- 網路連線是否正常
- Supabase 專案是否已暫停（免費版會自動暫停）

### Q: Line 推播失敗

**A:** 檢查：
- Channel Access Token 是否正確
- Line User ID 是否正確
- 使用者是否已加入您的 Line Official Account 好友

### Q: 爬蟲抓不到文章

**A:** 可能原因：
- RSS feed URL 已變更
- 網站結構已更新（Elsevier 爬蟲可能需要調整）
- 網站封鎖爬蟲（嘗試增加延遲）
- 過去 7 天內沒有新文章

### Q: 訊息過長被截斷

**A:** Line 單則訊息限制 5000 字元。程式會自動分批發送，如果仍有問題：
- 減少 `days_back` 參數（預設 7 天）
- 調整訊息格式

## 進階設定

### 修改抓取天數

編輯 `main.py`，找到：

```python
articles = scraper.fetch_articles(
    url=journal['url'],
    rss_url=journal.get('rss_url'),
    days_back=7  # 改為您想要的天數
)
```

### 新增自訂爬蟲

1. 在 `scrapers/` 目錄建立新的爬蟲類別
2. 繼承 `BaseScraper`
3. 實作 `fetch_articles()` 方法
4. 在 `main.py` 的 `scrapers` 字典中註冊

### 更改推播時間

修改 crontab 或工作排程器的設定即可。

## 支援

如有問題，請查看：
- 日誌檔案：`logs/journal_tracker_YYYYMMDD.log`
- Cron 日誌：`logs/cron.log`

## 授權

MIT License
