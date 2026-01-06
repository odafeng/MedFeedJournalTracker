"""
更新 Supabase 雲端資料庫中的期刊設定：
1. 移除所有 IEEE 期刊
2. 將 Surgical Endoscopy 移到 CRC 類別
"""

import os
from dotenv import load_dotenv

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

print("=" * 70)
print("📝 更新雲端資料庫期刊設定")
print("=" * 70)

# ===== 1. 移除所有 IEEE 期刊 =====
print("\n🔧 步驟 1: 移除所有 IEEE 期刊...")

try:
    # 查詢所有 IEEE 期刊
    ieee_response = db.client.table("journals").select("id, name").ilike("name", "%IEEE%").execute()
    ieee_journals = ieee_response.data
    
    if ieee_journals:
        print(f"   找到 {len(ieee_journals)} 個 IEEE 期刊：")
        for j in ieee_journals:
            print(f"   - {j['name']}")
        
        # 刪除 IEEE 期刊
        for j in ieee_journals:
            db.client.table("journals").delete().eq("id", j['id']).execute()
        
        print(f"   ✅ 已刪除 {len(ieee_journals)} 個 IEEE 期刊")
    else:
        print("   ⚠️ 沒有找到 IEEE 期刊")
        
except Exception as e:
    print(f"   ❌ 刪除 IEEE 期刊失敗: {e}")

# ===== 2. 將 Surgical Endoscopy 移到 CRC 類別 =====
print("\n🔧 步驟 2: 將 Surgical Endoscopy 移到 CRC 類別...")

try:
    # 查詢 Surgical Endoscopy
    se_response = db.client.table("journals").select("id, name, category").eq("name", "Surgical Endoscopy").execute()
    
    if se_response.data:
        journal = se_response.data[0]
        print(f"   找到期刊：{journal['name']}")
        print(f"   目前類別：{journal['category']}")
        
        # 更新類別
        db.client.table("journals").update({"category": "CRC"}).eq("id", journal['id']).execute()
        print(f"   ✅ 已將類別從 {journal['category']} 更新為 CRC")
    else:
        print("   ⚠️ 沒有找到 Surgical Endoscopy")
        
except Exception as e:
    print(f"   ❌ 更新 Surgical Endoscopy 失敗: {e}")

# ===== 3. 顯示更新後的統計 =====
print("\n" + "=" * 70)
print("📊 更新後的期刊統計")
print("=" * 70)

try:
    response = db.client.table("journals").select("category").execute()
    journals = response.data
    
    total = len(journals)
    crc_count = sum(1 for j in journals if j['category'] == 'CRC')
    sds_count = sum(1 for j in journals if j['category'] == 'SDS')
    
    print(f"\n   總計：{total} 個期刊")
    print(f"   CRC 類別：{crc_count} 個")
    print(f"   SDS 類別：{sds_count} 個")
    
except Exception as e:
    print(f"   ❌ 查詢統計失敗: {e}")

print("\n" + "=" * 70)
print("✅ 更新完成！")
print("=" * 70)
print("\n提示：執行 python3 list_cloud_journals.py 可查看完整期刊清單")
