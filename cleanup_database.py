"""
資料庫清理工具
用於手動清理舊資料或調整清理參數
"""

import os
import sys
from dotenv import load_dotenv
from database.supabase_client import SupabaseClient
from utils.logger import setup_logger


def main():
    """主程式入口。"""
    logger = setup_logger()
    
    logger.info("=" * 70)
    logger.info("資料庫清理工具")
    logger.info("=" * 70)
    
    # 載入環境變數
    env_files = ['.env', '.env.local', '.env.production']
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"已載入環境變數檔案: {env_file}")
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
        logger.error(f"SUPABASE_URL: {'✓' if supabase_url else '✗'}")
        logger.error(f"SUPABASE_KEY: {'✓' if supabase_key else '✗'}")
        sys.exit(1)
    
    # 連接資料庫
    try:
        db = SupabaseClient(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"連接 Supabase 失敗: {e}")
        sys.exit(1)
    
    # 顯示清理前的統計資訊
    logger.info("\n清理前的資料庫狀態：")
    stats_before = db.get_database_stats()
    for table, count in stats_before.items():
        logger.info(f"  {table}: {count} 筆")
    
    # 詢問使用者清理參數
    print("\n" + "=" * 70)
    print("清理參數設定")
    print("=" * 70)
    
    try:
        max_articles = int(input("要保留多少篇文章？（預設 100）: ") or "100")
        max_notifications = int(input("要保留多少筆通知記錄？（預設 500）: ") or "500")
        days_to_keep = int(input("要保留幾天內的資料？（預設 90）: ") or "90")
    except ValueError:
        logger.error("輸入格式錯誤，使用預設值")
        max_articles = 100
        max_notifications = 500
        days_to_keep = 90
    
    # 確認清理
    print(f"\n即將執行清理：")
    print(f"  - 保留最新 {max_articles} 篇文章")
    print(f"  - 保留最新 {max_notifications} 筆通知記錄")
    print(f"  - 保留 {days_to_keep} 天內的資料")
    
    confirm = input("\n確定要執行清理嗎？(y/N): ")
    
    if confirm.lower() != 'y':
        logger.info("已取消清理")
        sys.exit(0)
    
    # 執行清理
    try:
        logger.info("\n開始清理...")
        cleanup_result = db.cleanup_old_data(
            max_articles=max_articles,
            max_notifications=max_notifications,
            days_to_keep=days_to_keep
        )
        
        logger.info(f"\n清理完成！")
        logger.info(f"  刪除了 {cleanup_result['articles_deleted']} 篇文章")
        logger.info(f"  刪除了 {cleanup_result['notifications_deleted']} 筆通知記錄")
        
        # 顯示清理後的統計資訊
        logger.info("\n清理後的資料庫狀態：")
        stats_after = db.get_database_stats()
        for table, count in stats_after.items():
            logger.info(f"  {table}: {count} 筆")
        
    except Exception as e:
        logger.error(f"清理過程中發生錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程式被使用者中斷")
        sys.exit(0)
    except Exception as e:
        print(f"\n程式執行時發生未預期的錯誤: {e}")
        sys.exit(1)

