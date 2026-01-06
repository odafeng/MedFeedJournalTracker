"""
列出 Supabase 雲端資料庫中所有期刊的腳本。
"""

import os
from dotenv import load_dotenv
from tabulate import tabulate

# 載入環境變數
env_files = ['.env', '.env.local', '.env.production']
for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        break

# 連接 Supabase
from database.supabase_client import SupabaseClient

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = (
    os.getenv('SUPABASE_KEY') or 
    os.getenv('SUPABASE_API_KEY') or 
    os.getenv('SUPABASE_SERVICE_ROLE')
)

if not supabase_url or not supabase_key:
    print("❌ 錯誤：缺少 SUPABASE_URL 或 SUPABASE_KEY 環境變數")
    exit(1)

db = SupabaseClient(supabase_url, supabase_key)

# 查詢所有期刊
try:
    response = db.client.table("journals").select("*").order("category").order("name").execute()
    journals = response.data
except Exception as e:
    print(f"❌ 查詢失敗: {e}")
    exit(1)

# 統計資訊
total = len(journals)
active = sum(1 for j in journals if j.get('is_active', True))
inactive = total - active

# 按類別分組
categories = {}
for j in journals:
    cat = j.get('category', 'Unknown')
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(j)

# 輸出結果
print("=" * 80)
print("📚 Supabase 雲端資料庫 - 期刊清單")
print("=" * 80)
print(f"\n📊 總覽：共 {total} 個期刊（{active} 個啟用，{inactive} 個停用）\n")

for category, journal_list in sorted(categories.items()):
    print(f"\n{'='*80}")
    print(f"📁 類別：{category}（{len(journal_list)} 個期刊）")
    print("=" * 80)
    
    # 準備表格資料
    table_data = []
    for idx, j in enumerate(journal_list, 1):
        status = "✅" if j.get('is_active', True) else "❌"
        table_data.append([
            idx,
            j.get('name', 'N/A'),
            j.get('issn', 'N/A'),
            j.get('scraper_class', 'N/A'),
            status
        ])
    
    # 輸出表格
    headers = ["#", "期刊名稱", "ISSN", "爬蟲類型", "狀態"]
    print(tabulate(table_data, headers=headers, tablefmt="simple"))

print("\n" + "=" * 80)
print("查詢完成！")
print("=" * 80)
