# 資料庫自動清理功能 - 實作總結

## 📋 實作內容

本次實作了完整的資料庫自動清理功能，避免資料庫無限增長。

## 🆕 新增的檔案

### 1. `database/supabase_client.py`（更新）

新增了兩個方法：

#### `cleanup_old_data()`
- 自動清理舊文章和通知記錄
- 支援按數量或時間清理
- 預設保留最新 100 篇文章、500 筆通知記錄

#### `get_database_stats()`
- 取得資料庫統計資訊
- 顯示各表的資料筆數

### 2. `main.py`（更新）

- 新增步驟 8：清理舊資料
- 從設定檔讀取清理參數
- 支援啟用/停用自動清理
- 顯示清理前後的統計資訊

### 3. `config/cleanup_settings.json`（新增）

清理參數設定檔：
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

提供三種預設情境：
- 小型使用（50 篇文章、200 筆通知）
- 中型使用（100 篇文章、500 筆通知）
- 大型使用（200 篇文章、1000 筆通知）

### 4. `cleanup_database.py`（新增）

獨立的清理工具，功能：
- 互動式設定清理參數
- 確認後執行清理
- 顯示清理前後的統計資訊

使用方式：
```bash
python cleanup_database.py
```

### 5. `check_database_stats.py`（新增）

快速查看資料庫狀態的工具，顯示：
- 各表的資料筆數
- 估算的資料大小
- Supabase 使用率

使用方式：
```bash
python check_database_stats.py
```

### 6. `DATABASE_CLEANUP.md`（新增）

完整的清理功能文件，包含：
- 清理策略說明
- 使用指南
- 不同情境的建議設定
- 故障排除
- 常見問題

### 7. `README.md`（更新）

更新主要文件：
- 在功能特色中加入自動清理
- 在執行流程中加入清理步驟
- 新增「資料庫清理」章節

## 🎯 核心功能

### 自動清理機制

每次執行 `main.py` 時，會在推播通知後自動執行清理：

1. **文章表（articles）**
   - 優先按數量限制：只保留最新的 N 篇（預設 100）
   - 如果文章數少於限制，則保留 N 天內的文章（預設 90 天）
   - 按 `discovered_at` 欄位排序

2. **通知記錄表（notifications）**
   - 只保留最新的 N 筆記錄（預設 500）
   - 按 `sent_at` 欄位排序

3. **期刊表和訂閱者表**
   - 不自動清理（這些是基礎資料）

### 級聯刪除

刪除文章時，相關的通知記錄會自動被刪除（資料庫設定了 `ON DELETE CASCADE`）

## 📊 使用方式

### 1. 自動清理（推薦）

正常執行主程式即可：
```bash
python main.py
```

### 2. 查看資料庫狀態

```bash
python check_database_stats.py
```

### 3. 手動清理

```bash
python cleanup_database.py
```

### 4. 調整清理參數

編輯 `config/cleanup_settings.json`：
```json
{
  "cleanup": {
    "enabled": true,
    "max_articles": 100,        // 保留文章數
    "max_notifications": 500,   // 保留通知數
    "days_to_keep": 90          // 保留天數
  }
}
```

### 5. 停用自動清理

```json
{
  "cleanup": {
    "enabled": false
  }
}
```

## 💡 不同使用情境的建議

### 測試環境 / 個人使用
```json
{
  "max_articles": 50,
  "max_notifications": 200,
  "days_to_keep": 30
}
```

### 小團隊 / 一般使用（預設）
```json
{
  "max_articles": 100,
  "max_notifications": 500,
  "days_to_keep": 90
}
```

### 多團隊 / 長期保存
```json
{
  "max_articles": 200,
  "max_notifications": 1000,
  "days_to_keep": 180
}
```

## 📈 資料庫容量估算

### Supabase 免費方案限制
- 資料庫大小：500 MB
- 資料列數：無限制（但受大小限制）

### 預估大小
假設：
- 每篇文章平均 2 KB
- 每筆通知記錄平均 0.5 KB

計算（預設設定）：
- 100 篇文章 ≈ 200 KB
- 500 筆通知 ≈ 250 KB
- 總計 ≈ 450 KB（遠低於 500 MB）

## ✅ 測試檢查清單

- [ ] 執行 `python check_database_stats.py` 查看當前狀態
- [ ] 執行 `python cleanup_database.py` 測試手動清理
- [ ] 執行 `python main.py` 確認自動清理正常運作
- [ ] 檢查日誌檔案確認清理記錄
- [ ] 在 Supabase Dashboard 確認資料量變化

## 🔧 程式碼重點

### 清理方法簽名
```python
def cleanup_old_data(
    self, 
    max_articles: int = 100, 
    max_notifications: int = 500,
    days_to_keep: int = 90
) -> Dict[str, int]:
    """
    Returns:
        {
            'articles_deleted': N,
            'notifications_deleted': M
        }
    """
```

### 統計方法簽名
```python
def get_database_stats(self) -> Dict[str, int]:
    """
    Returns:
        {
            'journals': N,
            'subscribers': N,
            'articles': N,
            'notifications': N
        }
    """
```

## 📚 相關文件

1. **DATABASE_CLEANUP.md** - 完整的清理功能文件
2. **README.md** - 主要說明文件（已更新）
3. **config/cleanup_settings.json** - 清理參數設定

## 🎉 完成！

資料庫自動清理功能已完整實作，包括：
- ✅ 自動清理機制
- ✅ 手動清理工具
- ✅ 統計查看工具
- ✅ 彈性設定檔
- ✅ 完整文件

現在您的系統可以：
1. 每次執行時自動清理舊資料
2. 避免資料庫無限增長
3. 靈活調整清理參數
4. 隨時查看資料庫狀態

