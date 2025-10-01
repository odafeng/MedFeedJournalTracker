# 資料庫清理指南

## 概述

為了避免資料庫無限增長，本系統提供了自動清理機制，可以定期刪除舊資料。

## 清理策略

### 1. 文章表（articles）
- **數量限制**：只保留最新的 N 篇文章（預設 100 篇）
- **時間限制**：如果文章數少於限制，則保留最近 N 天內的文章（預設 90 天）
- **刪除規則**：按 `discovered_at` 欄位排序，刪除最舊的文章

### 2. 通知記錄表（notifications）
- **數量限制**：只保留最新的 N 筆記錄（預設 500 筆）
- **刪除規則**：按 `sent_at` 欄位排序，刪除最舊的記錄

### 3. 期刊表和訂閱者表
- **不自動清理**：這兩個表的資料通常是固定的，不會自動清理

## 自動清理

### 在主程式中自動執行

每次執行 `main.py` 時，會在推播通知後自動執行清理：

```bash
python main.py
```

清理參數可在程式碼中調整（`main.py` 第 339 行）：

```python
cleanup_result = db.cleanup_old_data(
    max_articles=100,        # 保留最新 100 篇文章
    max_notifications=500,   # 保留最新 500 筆通知
    days_to_keep=90          # 保留 90 天內的資料
)
```

### 調整清理參數

編輯 `config/cleanup_settings.json` 查看不同使用情境的建議設定：

```json
{
  "cleanup": {
    "enabled": true,
    "max_articles": 100,
    "max_notifications": 500,
    "days_to_keep": 90
  }
}
```

參數說明：
- `enabled`: 是否啟用自動清理（目前僅供參考）
- `max_articles`: 最多保留的文章數量
- `max_notifications`: 最多保留的通知記錄數量
- `days_to_keep`: 保留天數（當文章數少於 max_articles 時使用）

## 手動清理

### 使用清理工具

執行獨立的清理腳本：

```bash
python cleanup_database.py
```

這個腳本會：
1. 顯示目前資料庫狀態
2. 讓您設定清理參數
3. 詢問確認後執行清理
4. 顯示清理結果

範例輸出：

```
======================================================================
資料庫清理工具
======================================================================
已載入環境變數檔案: .env.local

清理前的資料庫狀態：
  journals: 13 筆
  subscribers: 2 筆
  articles: 156 筆
  notifications: 312 筆

======================================================================
清理參數設定
======================================================================
要保留多少篇文章？（預設 100）: 100
要保留多少筆通知記錄？（預設 500）: 500
要保留幾天內的資料？（預設 90）: 90

即將執行清理：
  - 保留最新 100 篇文章
  - 保留最新 500 筆通知記錄
  - 保留 90 天內的資料

確定要執行清理嗎？(y/N): y

開始清理...
清理完成！
  刪除了 56 篇文章
  刪除了 0 筆通知記錄

清理後的資料庫狀態：
  journals: 13 筆
  subscribers: 2 筆
  articles: 100 筆
  notifications: 312 筆
```

### 使用 Python 程式碼

```python
from database.supabase_client import SupabaseClient

# 初始化客戶端
db = SupabaseClient(supabase_url, supabase_key)

# 執行清理
result = db.cleanup_old_data(
    max_articles=100,        # 保留最新 100 篇文章
    max_notifications=500,   # 保留最新 500 筆通知
    days_to_keep=90          # 保留 90 天內的資料
)

print(f"刪除了 {result['articles_deleted']} 篇文章")
print(f"刪除了 {result['notifications_deleted']} 筆通知記錄")
```

## 查看資料庫統計

```python
from database.supabase_client import SupabaseClient

db = SupabaseClient(supabase_url, supabase_key)
stats = db.get_database_stats()

for table, count in stats.items():
    print(f"{table}: {count} 筆")
```

## 不同使用情境的建議設定

### 小型使用（節省空間）
適合：測試環境、個人使用

```python
cleanup_result = db.cleanup_old_data(
    max_articles=50,
    max_notifications=200,
    days_to_keep=30
)
```

### 中型使用（預設）
適合：小團隊、一般使用

```python
cleanup_result = db.cleanup_old_data(
    max_articles=100,
    max_notifications=500,
    days_to_keep=90
)
```

### 大型使用（長期保存）
適合：需要長期保存資料、多個團隊

```python
cleanup_result = db.cleanup_old_data(
    max_articles=200,
    max_notifications=1000,
    days_to_keep=180
)
```

## 注意事項

### 1. 級聯刪除

刪除文章時，相關的通知記錄也會被自動刪除（因為資料庫設定了 `ON DELETE CASCADE`）

```sql
-- 在 database/supabase_schema.sql 中
CREATE TABLE notifications (
    ...
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    ...
);
```

### 2. 備份建議

如果需要長期保存資料，建議定期備份資料庫：

- 在 Supabase Dashboard → Database → Backups
- 或使用 `pg_dump` 匯出資料

### 3. 效能考量

清理操作會掃描整個表，如果資料量很大，可能需要一些時間。建議在系統負載較低的時候執行清理（例如深夜）。

### 4. 執行時機

**自動清理**（每次執行 main.py）：
- 優點：自動化，不需要人工干預
- 缺點：每次都會執行，可能不必要

**手動清理**（定期執行 cleanup_database.py）：
- 優點：更靈活，可以選擇執行時機
- 缺點：需要記得定期執行

## Supabase 免費方案限制

Supabase 免費方案的限制：
- 資料庫大小：500 MB
- 資料列數：無限制（但受大小限制）

建議設定：
- 如果接近容量限制，請降低 `max_articles` 和 `max_notifications` 的值
- 定期監控資料庫使用量（在 Supabase Dashboard 查看）

### 估算資料庫大小

假設：
- 每篇文章平均 2 KB（包含標題、摘要、作者等）
- 每筆通知記錄平均 0.5 KB

計算：
- 100 篇文章 ≈ 200 KB
- 500 筆通知 ≈ 250 KB
- 總計 ≈ 450 KB（加上期刊和訂閱者資料）

所以預設設定遠低於 500 MB 的限制。

## 故障排除

### 清理失敗

如果清理失敗，檢查：
1. Supabase 連線是否正常
2. API Key 是否有足夠權限（建議使用 Service Role Key）
3. 日誌檔案中的錯誤訊息

### 資料庫持續增長

如果資料庫持續增長：
1. 確認清理功能是否正常執行
2. 檢查 `max_articles` 參數是否設定正確
3. 手動執行 `cleanup_database.py` 檢查

### 刪除的文章太多

如果清理刪除了太多文章：
1. 增加 `max_articles` 的值
2. 增加 `days_to_keep` 的值
3. 檢查是否有大量舊文章一次性進入系統

## 進階功能

### 只查看統計，不執行清理

修改 `cleanup_database.py`，註解掉執行清理的部分：

```python
# 執行清理
# cleanup_result = db.cleanup_old_data(...)
```

### 排程自動清理

在 cron 或 Windows Task Scheduler 中設定：

```bash
# 每週日凌晨 3 點執行清理
0 3 * * 0 cd /path/to/project && python cleanup_database.py
```

### 自訂清理規則

編輯 `database/supabase_client.py` 中的 `cleanup_old_data` 方法，加入自訂邏輯：

```python
# 例如：只刪除特定類別的文章
delete_response = self.client.table("articles").delete().eq(
    "category", "CRC"
).lt("discovered_at", cutoff_date).execute()
```

## 相關檔案

- `database/supabase_client.py` - 清理方法實作
- `main.py` - 自動清理整合
- `cleanup_database.py` - 獨立清理工具
- `config/cleanup_settings.json` - 清理參數設定
- `DATABASE_CLEANUP.md` - 本文件

## 常見問題

**Q: 清理會影響正在運行的系統嗎？**  
A: 不會。清理操作是在資料庫層面進行，不會影響正在執行的 main.py。

**Q: 可以恢復被刪除的資料嗎？**  
A: 無法直接恢復。建議定期備份資料庫。

**Q: 清理需要多久時間？**  
A: 通常幾秒鐘內完成，除非資料量非常大。

**Q: 可以關閉自動清理嗎？**  
A: 可以。註解掉 `main.py` 中的清理步驟即可。

**Q: 清理會刪除期刊和訂閱者資料嗎？**  
A: 不會。清理只針對文章和通知記錄表。

