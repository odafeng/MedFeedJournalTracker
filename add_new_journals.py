"""
新增期刊到 Supabase 雲端資料庫並測試 RSS feeds
"""

import os
from dotenv import load_dotenv

# 載入環境變數
env_files = ['.env', '.env.local', '.env.production']
for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        break

from database.supabase_client import SupabaseClient
from scrapers.rss_scraper import RSSScraper
from scrapers.pubmed_scraper import PubMedScraper

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = (
    os.getenv('SUPABASE_KEY') or 
    os.getenv('SUPABASE_API_KEY') or 
    os.getenv('SUPABASE_SERVICE_ROLE')
)
pubmed_api_key = os.getenv('PUBMED_API_KEY')

if not supabase_url or not supabase_key:
    print("❌ 錯誤：缺少 SUPABASE_URL 或 SUPABASE_KEY 環境變數")
    exit(1)

db = SupabaseClient(supabase_url, supabase_key)

# 要新增的期刊（所有 SDS 類別）
NEW_JOURNALS = [
    {
        "name": "Medical Image Analysis",
        "issn": "1361-8415",
        "url": "https://www.sciencedirect.com/journal/medical-image-analysis",
        "rss_url": None,  # Elsevier 無 RSS，使用 PubMed
        "publisher_type": "elsevier",
        "scraper_class": "PubMedScraper",
        "category": "SDS"
    },
    {
        "name": "International Journal of Computer Assisted Radiology and Surgery",
        "issn": "1861-6410",
        "url": "https://link.springer.com/journal/11548",
        "rss_url": "https://link.springer.com/search.rss?facet-content-type=Article&facet-journal-id=11548&channel-name=International%20Journal%20of%20Computer%20Assisted%20Radiology%20and%20Surgery",
        "publisher_type": "springer",
        "scraper_class": "RSSScraper",
        "category": "SDS"
    },
    {
        "name": "Computerized Medical Imaging and Graphics",
        "issn": "0895-6111",
        "url": "https://www.sciencedirect.com/journal/computerized-medical-imaging-and-graphics",
        "rss_url": None,  # Elsevier 無 RSS，使用 PubMed
        "publisher_type": "elsevier",
        "scraper_class": "PubMedScraper",
        "category": "SDS"
    },
    {
        "name": "International Journal of Medical Robotics and Computer Assisted Surgery",
        "issn": "1478-5951",
        "url": "https://onlinelibrary.wiley.com/journal/1478596x",
        "rss_url": "https://onlinelibrary.wiley.com/feed/1478596x/most-recent",
        "publisher_type": "wiley",
        "scraper_class": "RSSScraper",
        "category": "SDS"
    },
    {
        "name": "Quantitative Imaging in Medicine and Surgery",
        "issn": "2223-4292",
        "url": "https://qims.amegroups.org/",
        "rss_url": "https://qims.amegroups.org/rss",
        "publisher_type": "ame",
        "scraper_class": "RSSScraper",
        "category": "SDS"
    }
]

print("=" * 80)
print("📝 新增期刊到雲端資料庫")
print("=" * 80)

# ===== 1. 新增期刊 =====
print("\n🔧 步驟 1: 新增期刊到資料庫...")

added_count = 0
skipped_count = 0

for journal in NEW_JOURNALS:
    try:
        # 檢查是否已存在
        existing = db.client.table("journals").select("id").eq("issn", journal["issn"]).execute()
        
        if existing.data:
            print(f"   ⏭️  {journal['name']} 已存在，跳過")
            skipped_count += 1
        else:
            # 新增期刊
            db.client.table("journals").insert({
                "name": journal["name"],
                "issn": journal["issn"],
                "url": journal["url"],
                "rss_url": journal["rss_url"],
                "publisher_type": journal["publisher_type"],
                "scraper_class": journal["scraper_class"],
                "category": journal["category"],
                "is_active": True
            }).execute()
            print(f"   ✅ 已新增：{journal['name']}")
            added_count += 1
            
    except Exception as e:
        print(f"   ❌ 新增失敗 ({journal['name']}): {e}")

print(f"\n   📊 新增 {added_count} 個，跳過 {skipped_count} 個（已存在）")

# ===== 2. 測試爬蟲 =====
print("\n" + "=" * 80)
print("🧪 步驟 2: 測試期刊爬蟲")
print("=" * 80)

rss_scraper = RSSScraper()
pubmed_scraper = PubMedScraper(api_key=pubmed_api_key)

for journal in NEW_JOURNALS:
    print(f"\n📖 測試: {journal['name']}")
    print(f"   爬蟲: {journal['scraper_class']}")
    
    try:
        if journal['scraper_class'] == 'PubMedScraper':
            articles = pubmed_scraper.fetch_articles(
                url=journal['url'],
                rss_url=journal['rss_url'],
                days_back=30,
                journal_issn=journal['issn'],
                journal_name=journal['name']
            )
        else:
            articles = rss_scraper.fetch_articles(
                url=journal['url'],
                rss_url=journal['rss_url'],
                days_back=30
            )
        
        if articles:
            print(f"   ✅ 成功！找到 {len(articles)} 篇文章")
            # 顯示第一篇文章
            first = articles[0]
            title = first.get('title', 'N/A')
            if len(title) > 60:
                title = title[:60] + "..."
            print(f"   📄 範例: {title}")
        else:
            print(f"   ⚠️  沒有找到文章（可能最近沒有更新）")
            
    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")

# ===== 3. 顯示最終統計 =====
print("\n" + "=" * 80)
print("📊 最終期刊統計")
print("=" * 80)

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

print("\n" + "=" * 80)
print("✅ 完成！")
print("=" * 80)
