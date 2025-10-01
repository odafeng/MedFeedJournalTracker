"""
Journal Tracker - 主程式
自動追蹤學術期刊最新文章，並推播到 Line Messaging API。
"""

import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List

from database.supabase_client import SupabaseClient
from scrapers.rss_scraper import RSSScraper
from scrapers.ieee_rss_scraper import IEEERSSScraper
from scrapers.elsevier_scraper import ElsevierScraper
from notifier.line_notifier import LineNotifier
from utils.logger import setup_logger


def load_config(config_path: str) -> dict:
    """
    載入 JSON 設定檔。
    
    Args:
        config_path: 設定檔路徑
    
    Returns:
        dict: 設定檔內容
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"設定檔不存在: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"設定檔格式錯誤: {e}")
        sys.exit(1)


def organize_articles_by_category(articles: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
    """
    將文章按類別和期刊分組。
    
    Args:
        articles: 文章列表
    
    Returns:
        Dict[str, Dict[str, List[Dict]]]: 按類別和期刊分組的文章
            格式: {
                'CRC': {journal_name: [articles]},
                'SDS': {journal_name: [articles]}
            }
    """
    result = {}
    
    for article in articles:
        category = article['category']
        journal_name = article['journal_name']
        
        # 初始化類別
        if category not in result:
            result[category] = {}
        
        # 初始化期刊
        if journal_name not in result[category]:
            result[category][journal_name] = []
        
        # 加入文章
        result[category][journal_name].append(article)
    
    return result


def main():
    """主程式入口。"""
    start_time = datetime.now()
    
    # ===== 1. 初始化 =====
    logger.info("=" * 70)
    logger.info("Journal Tracker 開始執行")
    logger.info(f"執行時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)
    
    # 載入環境變數（嘗試多個 .env 檔案）
    env_files = ['.env', '.env.local', '.env.production']
    env_loaded = False
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"已載入環境變數檔案: {env_file}")
            env_loaded = True
            break
    
    if not env_loaded:
        logger.warning("未找到環境變數檔案，使用系統環境變數")
    
    # 檢查必要的環境變數
    supabase_url = os.getenv('SUPABASE_URL')
    # 支援多種 key 名稱
    supabase_key = (
        os.getenv('SUPABASE_KEY') or 
        os.getenv('SUPABASE_API_KEY') or 
        os.getenv('SUPABASE_SERVICE_ROLE')
    )
    line_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    
    if not all([supabase_url, supabase_key, line_token]):
        logger.error("缺少必要的環境變數！")
        logger.error(f"SUPABASE_URL: {'✓' if supabase_url else '✗'}")
        logger.error(f"SUPABASE_KEY: {'✓' if supabase_key else '✗'}")
        logger.error(f"LINE_CHANNEL_ACCESS_TOKEN: {'✓' if line_token else '✗'}")
        sys.exit(1)
    
    # ===== 2. 載入設定 =====
    logger.info("\n載入設定檔...")
    journals_config = load_config('config/journals.json')
    subscribers_config = load_config('config/subscribers.json')
    
    # 載入清理設定（選用）
    try:
        cleanup_config = load_config('config/cleanup_settings.json')
        cleanup_settings = cleanup_config.get('cleanup', {})
        logger.info(f"載入清理設定: 保留 {cleanup_settings.get('max_articles', 100)} 篇文章")
    except:
        # 如果沒有清理設定檔，使用預設值
        cleanup_settings = {
            'enabled': True,
            'max_articles': 100,
            'max_notifications': 500,
            'days_to_keep': 90
        }
        logger.info("使用預設清理設定")
    
    logger.info(f"載入 {len(journals_config['journals'])} 個期刊設定")
    logger.info(f"載入 {len(subscribers_config['subscribers'])} 個訂閱者設定")
    
    # ===== 3. 連接服務 =====
    logger.info("\n連接外部服務...")
    
    try:
        db = SupabaseClient(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"連接 Supabase 失敗: {e}")
        sys.exit(1)
    
    try:
        notifier = LineNotifier(line_token)
    except Exception as e:
        logger.error(f"初始化 Line 通知器失敗: {e}")
        sys.exit(1)
    
    # ===== 4. 同步設定資料到資料庫 =====
    logger.info("\n同步資料到資料庫...")
    
    try:
        db.sync_journals(journals_config['journals'])
        db.sync_subscribers(subscribers_config['subscribers'])
    except Exception as e:
        logger.error(f"同步資料失敗: {e}")
        sys.exit(1)
    
    # ===== 5. 初始化爬蟲 =====
    try:
        scrapers = {
            'RSSScraper': RSSScraper(),
            'IEEERSSScraper': IEEERSSScraper(),
            'ElsevierScraper': ElsevierScraper()
        }
        logger.info(f"已初始化 {len(scrapers)} 個爬蟲")
    except Exception as e:
        logger.error(f"初始化爬蟲失敗: {e}")
        sys.exit(1)
    
    # ===== 6. 抓取文章 =====
    logger.info("\n" + "=" * 70)
    logger.info("開始抓取文章")
    logger.info("=" * 70)
    
    all_new_articles = []
    
    try:
        journals = db.get_active_journals()
        logger.info(f"取得 {len(journals)} 個啟用的期刊")
        
        for idx, journal in enumerate(journals, 1):
            logger.info(f"\n[{idx}/{len(journals)}] 處理期刊: {journal['name']}")
            logger.info(f"  類別: {journal['category']}")
            logger.info(f"  爬蟲: {journal['scraper_class']}")
            
            # 選擇對應的爬蟲
            scraper_class = journal['scraper_class']
            if scraper_class not in scrapers:
                logger.error(f"  找不到爬蟲: {scraper_class}")
                continue
            
            scraper = scrapers[scraper_class]
            
            try:
                # 抓取文章
                articles = scraper.fetch_articles(
                    url=journal['url'],
                    rss_url=journal.get('rss_url'),
                    days_back=7
                )
                
                logger.info(f"  抓取到 {len(articles)} 篇文章")
                
                # 過濾新文章（檢查 DOI 是否已存在）
                new_articles = []
                for article in articles:
                    if not db.article_exists(article['doi']):
                        new_articles.append(article)
                
                logger.info(f"  其中 {len(new_articles)} 篇是新文章")
                
                if new_articles:
                    # 加上 journal_id、category 和 journal_name
                    for article in new_articles:
                        article['journal_id'] = journal['id']
                        article['category'] = journal['category']
                        article['journal_name'] = journal['name']
                    
                    # 存入資料庫
                    inserted = db.insert_articles(new_articles)
                    
                    # 確保插入後的文章也有 journal_name（從原始文章複製）
                    for i, inserted_article in enumerate(inserted):
                        if i < len(new_articles):
                            inserted_article['journal_name'] = new_articles[i]['journal_name']
                    
                    all_new_articles.extend(inserted)
                    logger.info(f"  ✓ 成功儲存 {len(inserted)} 篇新文章")
                
            except Exception as e:
                logger.error(f"  ✗ 處理期刊時發生錯誤: {e}")
                continue
    
    except Exception as e:
        logger.error(f"抓取文章過程中發生錯誤: {e}")
    
    # ===== 7. 推播通知 =====
    logger.info("\n" + "=" * 70)
    logger.info("推播通知")
    logger.info("=" * 70)
    
    if not all_new_articles:
        logger.info("沒有新文章，不需要推播通知")
    else:
        logger.info(f"共有 {len(all_new_articles)} 篇新文章需要推播")
        
        try:
            # 取得所有啟用的訂閱者
            subscribers = db.get_active_subscribers()
            logger.info(f"取得 {len(subscribers)} 個啟用的訂閱者")
            
            if not subscribers:
                logger.warning("沒有啟用的訂閱者")
            else:
                # 將文章按類別和期刊分組
                articles_by_category = organize_articles_by_category(all_new_articles)
                
                logger.info(f"\n文章分佈:")
                for category, journals_dict in articles_by_category.items():
                    total = sum(len(articles) for articles in journals_dict.values())
                    logger.info(f"  {category}: {total} 篇文章，來自 {len(journals_dict)} 個期刊")
                
                # 逐一推播給訂閱者
                success_count = 0
                fail_count = 0
                
                for subscriber in subscribers:
                    logger.info(f"\n處理訂閱者: {subscriber['name']}")
                    logger.info(f"  Line User ID: {subscriber['line_user_id']}")
                    logger.info(f"  訂閱類別: {subscriber['subscribed_category']}")
                    
                    # 篩選該訂閱者感興趣的文章（只有相同類別）
                    category = subscriber['subscribed_category']
                    articles_by_journal = articles_by_category.get(category, {})
                    
                    if not articles_by_journal:
                        logger.info(f"  沒有符合類別 {category} 的新文章")
                        continue
                    
                    # 計算文章數量
                    article_count = sum(
                        len(articles) for articles in articles_by_journal.values()
                    )
                    logger.info(f"  將推播 {article_count} 篇 {category} 類別的文章")
                    
                    # 格式化訊息
                    try:
                        message = notifier.format_message(
                            subscriber['name'],
                            category,
                            articles_by_journal
                        )
                        
                        # 推播
                        success = notifier.send_notification(
                            subscriber['line_user_id'], 
                            message
                        )
                        
                        if success:
                            logger.info(f"  ✓ 推播成功")
                            success_count += 1
                            
                            # 記錄推播狀態到資料庫（針對每篇文章）
                            for articles in articles_by_journal.values():
                                for article in articles:
                                    db.insert_notification(
                                        article['id'],
                                        subscriber['id'],
                                        status='success'
                                    )
                        else:
                            logger.error(f"  ✗ 推播失敗")
                            fail_count += 1
                            
                            # 記錄失敗狀態
                            for articles in articles_by_journal.values():
                                for article in articles:
                                    db.insert_notification(
                                        article['id'],
                                        subscriber['id'],
                                        status='failed',
                                        error_message='推播失敗'
                                    )
                    
                    except Exception as e:
                        logger.error(f"  ✗ 推播過程發生錯誤: {e}")
                        fail_count += 1
                
                logger.info(f"\n推播結果: 成功 {success_count} 個，失敗 {fail_count} 個")
        
        except Exception as e:
            logger.error(f"推播通知過程中發生錯誤: {e}")
    
    # ===== 8. 清理舊資料 =====
    if cleanup_settings.get('enabled', True):
        logger.info("\n" + "=" * 70)
        logger.info("清理舊資料")
        logger.info("=" * 70)
        
        try:
            # 顯示清理前的統計資訊
            logger.info("清理前的資料庫狀態：")
            stats_before = db.get_database_stats()
            for table, count in stats_before.items():
                logger.info(f"  {table}: {count} 筆")
            
            # 執行清理（使用設定檔中的參數）
            cleanup_result = db.cleanup_old_data(
                max_articles=cleanup_settings.get('max_articles', 100),
                max_notifications=cleanup_settings.get('max_notifications', 500),
                days_to_keep=cleanup_settings.get('days_to_keep', 90)
            )
            
            # 顯示清理後的統計資訊
            logger.info("\n清理後的資料庫狀態：")
            stats_after = db.get_database_stats()
            for table, count in stats_after.items():
                logger.info(f"  {table}: {count} 筆")
            
        except Exception as e:
            logger.error(f"清理資料過程中發生錯誤: {e}")
    else:
        logger.info("\n自動清理已停用（可在 config/cleanup_settings.json 中啟用）")
    
    # ===== 9. 執行總結 =====
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 70)
    logger.info("執行完成")
    logger.info("=" * 70)
    logger.info(f"開始時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"執行時長: {duration:.2f} 秒")
    logger.info(f"新文章數: {len(all_new_articles)}")
    logger.info("=" * 70)


if __name__ == "__main__":
    # 設定 logger
    logger = setup_logger()
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n程式被使用者中斷")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程式執行時發生未預期的錯誤: {e}", exc_info=True)
        sys.exit(1)
