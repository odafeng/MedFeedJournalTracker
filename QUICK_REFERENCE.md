# 快速參考指南

## 常用命令

### 執行主程式
```bash
# 正常執行（包含自動清理）
python main.py

# 查看即時輸出
python main.py | tee -a logs/manual_run.log
```

### 資料庫管理

```bash
# 查看資料庫狀態
python check_database_stats.py

# 手動清理資料庫
python cleanup_database.py
```

### 測試和驗證

```bash
# 測試爬蟲功能
python test_scrapers.py

# 驗證期刊設定
python verify_journals.py

# 驗證 RSS feeds
python verify_rss_feeds.py

# 取得 Line User ID
python get_user_id.py
```

## 設定檔位置

| 檔案 | 用途 |
|------|------|
| `.env.local` | 環境變數（API keys） |
| `config/journals.json` | 期刊設定 |
| `config/subscribers.json` | 訂閱者設定 |
| `config/cleanup_settings.json` | 清理參數設定 |

## 日誌檔案

```bash
# 查看最新日誌
tail -f logs/journal_tracker_$(date +%Y%m%d).log

# 查看錯誤訊息
grep "ERROR" logs/journal_tracker_*.log

# 查看清理記錄
grep "清理" logs/journal_tracker_*.log
```

## 清理功能快速參考

### 預設清理參數
- 保留最新 **100 篇**文章
- 保留最新 **500 筆**通知記錄
- 保留 **90 天**內的資料

### 調整清理參數

編輯 `config/cleanup_settings.json`：

```json
{
  "cleanup": {
    "enabled": true,              // 啟用自動清理
    "max_articles": 100,          // 保留文章數
    "max_notifications": 500,     // 保留通知數
    "days_to_keep": 90            // 保留天數
  }
}
```

### 停用自動清理

```json
{
  "cleanup": {
    "enabled": false
  }
}
```

## 常見任務

### 新增訂閱者

1. 取得 Line User ID：
   ```bash
   python get_user_id.py
   ```

2. 編輯 `config/subscribers.json`：
   ```json
   {
     "name": "新訂閱者",
     "line_user_id": "User123456789",
     "subscribed_category": "CRC"
   }
   ```

3. 執行主程式同步：
   ```bash
   python main.py
   ```

### 新增期刊

1. 編輯 `config/journals.json`

2. 測試新期刊：
   ```bash
   python test_scrapers.py
   ```

3. 執行主程式同步：
   ```bash
   python main.py
   ```

### 檢查資料庫容量

```bash
python check_database_stats.py
```

輸出會顯示：
- 各表的資料筆數
- 估算的資料大小
- Supabase 使用率

### 手動清理資料庫

```bash
python cleanup_database.py
```

互動式設定清理參數，確認後執行。

## 排程執行

### Linux/Mac (cron)

```bash
# 編輯 crontab
crontab -e

# 每天早上 8:00 執行
0 8 * * * cd /path/to/project && python main.py
```

### Windows (Task Scheduler)

```bash
# 使用提供的腳本設定
setup_cron.bat
```

## 故障排除

### 查看錯誤日誌
```bash
grep "ERROR" logs/journal_tracker_*.log | tail -20
```

### 測試 Supabase 連線
```bash
python check_database_stats.py
```

### 測試 Line API
```bash
python get_user_id.py
```

### 測試爬蟲
```bash
python test_scrapers.py
```

## 資料備份

### 從 Supabase Dashboard
1. 登入 Supabase
2. Database → Backups
3. 下載備份

### 使用 pg_dump（進階）
```bash
pg_dump -h db.xxx.supabase.co -U postgres -d postgres > backup.sql
```

## 更新系統

```bash
# 拉取最新程式碼
git pull

# 更新 Python 套件
pip install -r requirements.txt --upgrade

# 測試執行
python main.py
```

## 環境變數檢查

```bash
# 檢查必要的環境變數是否存在
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.local')

vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'LINE_CHANNEL_ACCESS_TOKEN']
for v in vars:
    status = '✓' if os.getenv(v) else '✗'
    print(f'{status} {v}')
"
```

## 清理舊日誌

```bash
# 刪除 30 天前的日誌
find logs/ -name "*.log" -mtime +30 -delete

# 或在 Windows PowerShell
Get-ChildItem logs/*.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | Remove-Item
```

## 效能優化

### 減少 API 呼叫
- 調整 `days_back` 參數（main.py 第 190 行）
- 預設為 7 天，可改為 3 天減少抓取量

### 減少資料庫容量
- 降低 `max_articles` 和 `max_notifications`
- 在 `config/cleanup_settings.json` 調整

### 加快執行速度
- 減少追蹤的期刊數量
- 使用更快的網路連線

## 有用的連結

- [Supabase Dashboard](https://supabase.com/dashboard)
- [Line Developers Console](https://developers.line.biz/console/)
- [DATABASE_CLEANUP.md](DATABASE_CLEANUP.md) - 清理功能詳細文件
- [README.md](README.md) - 主要說明文件
- [INSTALL.md](INSTALL.md) - 安裝指南

## 緊急處理

### 系統無法執行
1. 檢查環境變數
2. 檢查網路連線
3. 查看錯誤日誌
4. 測試各個組件

### 資料庫滿了
```bash
# 立即手動清理
python cleanup_database.py

# 或調整參數後重新執行
python main.py
```

### Line 推播失敗
1. 檢查 LINE_CHANNEL_ACCESS_TOKEN
2. 確認 Line User ID 正確
3. 查看日誌中的錯誤訊息

## 聯絡資訊

如有問題，請檢查：
1. 錯誤日誌
2. README.md
3. DATABASE_CLEANUP.md
4. 相關的 Python 檔案註解

