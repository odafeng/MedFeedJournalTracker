"""
快速查看資料庫統計資訊
"""

import os
from dotenv import load_dotenv
from database.supabase_client import SupabaseClient
from utils.logger import setup_logger


def main():
    """主程式入口。"""
    logger = setup_logger()
    
    # 載入環境變數
    env_files = ['.env', '.env.local', '.env.production']
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            break
    
    # 檢查必要的環境變數
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = (
        os.getenv('SUPABASE_KEY') or 
        os.getenv('SUPABASE_API_KEY') or 
        os.getenv('SUPABASE_SERVICE_ROLE')
    )
    
    if not all([supabase_url, supabase_key]):
        logger.error("缺少必要的環境變數！")
        return
    
    # 連接資料庫
    try:
        db = SupabaseClient(supabase_url, supabase_key)
        
        print("\n" + "=" * 70)
        print("資料庫統計資訊")
        print("=" * 70)
        
        stats = db.get_database_stats()
        
        print(f"\n📊 目前資料量：")
        for table, count in stats.items():
            print(f"  {table:20s}: {count:6d} 筆")
        
        # 估算大小
        estimated_size_kb = (
            stats.get('articles', 0) * 2 +  # 每篇文章約 2 KB
            stats.get('notifications', 0) * 0.5  # 每筆通知約 0.5 KB
        )
        
        print(f"\n💾 估算資料大小：")
        print(f"  文章表: {stats.get('articles', 0) * 2:.1f} KB")
        print(f"  通知表: {stats.get('notifications', 0) * 0.5:.1f} KB")
        print(f"  總計: {estimated_size_kb:.1f} KB ({estimated_size_kb/1024:.2f} MB)")
        
        print(f"\n📈 Supabase 免費方案限制：500 MB")
        print(f"  使用率: {estimated_size_kb/1024/500*100:.2f}%")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        logger.error(f"查詢失敗: {e}")


if __name__ == "__main__":
    main()

