# 部署 Journal Tracker 到 Render.com

## 🎯 優點

將整個系統部署到雲端的好處：

- ✅ **不需要本地電腦一直開著**
- ✅ **自動執行**：Render Cron Job 每天自動執行
- ✅ **高可靠性**：雲端服務 99.9% 在線
- ✅ **完全免費**：Render 免費版足夠使用
- ✅ **易於監控**：在 Dashboard 查看執行日誌
- ✅ **環境隔離**：不影響本地環境

---

## 📋 部署步驟

### 步驟 1: 準備 GitHub 儲存庫

#### 1.1 建立新的 GitHub 儲存庫

1. 前往 https://github.com/new
2. 儲存庫名稱：`journal-tracker`
3. 設定為 **Public**（Render 免費版需要）
4. 點擊「Create repository」

#### 1.2 上傳專案

在專案目錄執行：

```bash
cd C:\Users\KHUser\OneDrive\Desktop\journal_tracker

# 初始化 git（如果還沒有）
git init

# 加入所有檔案（.gitignore 會自動排除敏感檔案）
git add .
git commit -m "Initial commit: Journal Tracker system"

# 連接到 GitHub
git remote add origin https://github.com/您的帳號/journal-tracker.git
git branch -M main
git push -u origin main
```

### 步驟 2: 在 Render 建立 Cron Job

#### 2.1 前往 Render Dashboard

1. 登入 https://render.com/
2. 點擊 **「New +」**
3. 選擇 **「Cron Job」**

#### 2.2 連接儲存庫

1. 點擊「Connect a repository」
2. 找到 `journal-tracker` 儲存庫
3. 點擊「Connect」

#### 2.3 設定 Cron Job

**基本設定**：
- **Name**: `journal-tracker-daily`
- **Region**: Singapore（或最近的）
- **Branch**: `main`
- **Runtime**: **Python 3**

**命令設定**：
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`

**排程設定**：
- **Schedule**: `0 0 * * *`（每天 UTC 0:00 = 台灣時間早上 8:00）
  
⚠️ **時區注意**：
- Render 使用 UTC 時區
- 台灣時間 = UTC + 8 小時
- 台灣早上 8:00 = UTC 0:00

**環境變數**（重要！）：

點擊「Add Environment Variable」，逐一加入：

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | 您的 Supabase URL |
| `SUPABASE_SERVICE_ROLE` | 您的 Supabase Service Role Key |
| `LINE_CHANNEL_ACCESS_TOKEN` | 您的 Line Channel Access Token |
| `LOG_LEVEL` | `INFO` |

#### 2.4 建立服務

點擊 **「Create Cron Job」**

---

### 步驟 3: 驗證部署

#### 3.1 等待首次部署

- Render 會自動執行首次建置
- 需要 2-5 分鐘
- 在 Dashboard 可以看到部署日誌

#### 3.2 手動觸發測試

在 Render Dashboard：
1. 選擇您的 Cron Job
2. 點擊 **「Trigger Run」** 手動執行一次
3. 查看執行日誌
4. 確認：
   - ✅ 連接 Supabase 成功
   - ✅ 同步期刊和訂閱者成功
   - ✅ 抓取文章成功
   - ✅ 推播成功

#### 3.3 檢查 Line 推播

查看您的 Line 是否收到推播訊息。

---

## 🎯 完成後的系統架構

```
完全雲端化的 Journal Tracker

[Render Cron Job]                    [Render Web Service]
每天自動執行                          Webhook 服務
    ↓                                      ↓
抓取 13 個期刊                        收集 Line User IDs
    ↓                                      ↓
儲存到 Supabase                       提供網頁介面
    ↓                                      
推播到 Line                           
    ↓
訂閱者收到通知
```

**優點**：
- ✅ 完全不依賴本地電腦
- ✅ 兩個服務都在雲端運行
- ✅ 高可靠性、零維護

---

## ⚙️ Cron 排程說明

### Cron 表達式格式

```
* * * * *
│ │ │ │ │
│ │ │ │ └─ 星期幾 (0-7, 0 和 7 都是星期日)
│ │ │ └─── 月份 (1-12)
│ │ └───── 日期 (1-31)
│ └─────── 小時 (0-23)
└───────── 分鐘 (0-59)
```

### 常用排程範例

| 排程 | Cron 表達式 | 說明 |
|------|-----------|------|
| 每天早上 8:00（台灣） | `0 0 * * *` | UTC 0:00 = 台灣 8:00 |
| 每天下午 4:00（台灣） | `0 8 * * *` | UTC 8:00 = 台灣 16:00 |
| 每天兩次（早晚） | `0 0,12 * * *` | UTC 0:00 和 12:00 |
| 每週一早上 8:00 | `0 0 * * 1` | 每週一 |
| 每 12 小時 | `0 */12 * * *` | 每 12 小時 |

### 時區轉換

Render 使用 **UTC 時區**，台灣是 **UTC+8**：

```
台灣時間 8:00  = UTC 0:00  → Cron: 0 0 * * *  ✅（目前設定）
台灣時間 12:00 = UTC 4:00  → Cron: 0 4 * * *
台灣時間 16:00 = UTC 8:00  → Cron: 0 8 * * *
台灣時間 20:00 = UTC 12:00 → Cron: 0 12 * * *
```

---

## 🔧 管理與監控

### 查看執行日誌

在 Render Dashboard：
1. 選擇您的 Cron Job
2. 點擊「Logs」頁籤
3. 查看每次執行的完整日誌

### 手動觸發執行

不想等到排程時間，立即執行：
1. 在 Render Dashboard
2. 點擊「Trigger Run」按鈕
3. 立即執行一次

### 暫停/恢復排程

- **暫停**：在 Render Dashboard 可以停用 Cron Job
- **恢復**：重新啟用即可

### 修改排程時間

1. 在 Render Dashboard
2. Settings → Schedule
3. 修改 Cron 表達式
4. 儲存

---

## 📊 費用說明

### Render.com 免費版限制

**Cron Jobs**：
- ✅ 完全免費
- ✅ 無執行次數限制
- ✅ 單次執行時間：最多 1 小時（我們只需 30 秒）
- ⚠️ 沒有持久化儲存（但我們用 Supabase，不需要）

**總結**：完全夠用，不需要付費！

---

## 🆚 本地執行 vs 雲端部署

| 項目 | 本地執行 | Render Cron Job |
|------|---------|----------------|
| **電腦需求** | 需要一直開著 | 不需要 ✅ |
| **設定複雜度** | 簡單 | 需要上傳 GitHub |
| **可靠性** | 取決於電腦 | 99.9% 在線 ✅ |
| **監控** | 查看本地日誌 | Dashboard 即時查看 ✅ |
| **費用** | 電費 | 完全免費 ✅ |
| **彈性** | 可隨時修改 | 需要推送 GitHub |

**建議**：
- 測試期間：本地執行
- 正式使用：**部署到 Render** ⭐

---

## ⚡ 立即部署

準備好部署了嗎？

### 快速檢查清單

- [ ] 已測試本地執行成功
- [ ] 已確認能收到 Line 推播
- [ ] 有 GitHub 帳號
- [ ] 有 Render.com 帳號
- [ ] 準備好環境變數（Supabase + Line）

### 開始部署

1. **上傳到 GitHub**（如果還沒有）
2. **在 Render 建立 Cron Job**
3. **設定環境變數**
4. **測試執行**

**需要我一步步指導您完成部署嗎？** 🚀

---

最後更新: 2025-10-01
