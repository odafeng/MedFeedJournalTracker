"""Supabase client for database operations."""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client
import logging

logger = logging.getLogger("journal_tracker")


class SupabaseClient:
    """Supabase 資料庫客戶端，處理所有資料庫操作。"""
    
    def __init__(self, url: str, key: str):
        """
        初始化 Supabase 客戶端。
        
        Args:
            url: Supabase 專案 URL
            key: Supabase API Key (anon key 或 service role key)
        """
        self.client: Client = create_client(url, key)
        logger.info("Supabase 客戶端初始化成功")
    
    def sync_journals(self, journals: List[Dict]) -> None:
        """
        同步期刊資料到 Supabase（upsert 操作）。
        
        Args:
            journals: 期刊資料列表，每個包含 name, issn, url, rss_url, 
                     publisher_type, scraper_class, category
        """
        try:
            for journal in journals:
                # 檢查期刊是否已存在（使用 ISSN 作為唯一識別）
                existing = self.client.table("journals").select("*").eq(
                    "issn", journal["issn"]
                ).execute()
                
                journal_data = {
                    "name": journal["name"],
                    "issn": journal["issn"],
                    "url": journal["url"],
                    "rss_url": journal.get("rss_url"),
                    "publisher_type": journal["publisher_type"],
                    "scraper_class": journal["scraper_class"],
                    "category": journal["category"],
                    "is_active": True,
                    "updated_at": datetime.now().isoformat()
                }
                
                if existing.data:
                    # 更新現有期刊
                    self.client.table("journals").update(journal_data).eq(
                        "issn", journal["issn"]
                    ).execute()
                    logger.debug(f"更新期刊: {journal['name']}")
                else:
                    # 插入新期刊
                    self.client.table("journals").insert(journal_data).execute()
                    logger.debug(f"新增期刊: {journal['name']}")
            
            logger.info(f"成功同步 {len(journals)} 個期刊")
        except Exception as e:
            logger.error(f"同步期刊失敗: {e}")
            raise
    
    def sync_subscribers(self, subscribers: List[Dict]) -> None:
        """
        同步訂閱者資料到 Supabase（upsert 操作）。
        
        Args:
            subscribers: 訂閱者資料列表，每個包含 name, line_user_id, subscribed_category
        """
        try:
            for subscriber in subscribers:
                # 檢查訂閱者是否已存在（使用 line_user_id + subscribed_category 作為唯一識別）
                existing = self.client.table("subscribers").select("*").eq(
                    "line_user_id", subscriber["line_user_id"]
                ).eq(
                    "subscribed_category", subscriber["subscribed_category"]
                ).execute()
                
                subscriber_data = {
                    "name": subscriber["name"],
                    "line_user_id": subscriber["line_user_id"],
                    "subscribed_category": subscriber["subscribed_category"],
                    "is_active": True,
                    "updated_at": datetime.now().isoformat()
                }
                
                if existing.data:
                    # 更新現有訂閱者
                    self.client.table("subscribers").update(subscriber_data).eq(
                        "line_user_id", subscriber["line_user_id"]
                    ).eq(
                        "subscribed_category", subscriber["subscribed_category"]
                    ).execute()
                    logger.debug(f"更新訂閱者: {subscriber['name']} ({subscriber['subscribed_category']})")
                else:
                    # 插入新訂閱者
                    self.client.table("subscribers").insert(subscriber_data).execute()
                    logger.debug(f"新增訂閱者: {subscriber['name']} ({subscriber['subscribed_category']})")
            
            logger.info(f"成功同步 {len(subscribers)} 個訂閱者")
        except Exception as e:
            logger.error(f"同步訂閱者失敗: {e}")
            raise
    
    def get_active_journals(self) -> List[Dict]:
        """
        取得所有啟用的期刊。
        
        Returns:
            List[Dict]: 期刊資料列表
        """
        try:
            response = self.client.table("journals").select("*").eq(
                "is_active", True
            ).execute()
            
            logger.info(f"取得 {len(response.data)} 個啟用的期刊")
            return response.data
        except Exception as e:
            logger.error(f"取得期刊失敗: {e}")
            raise
    
    def get_active_subscribers(self) -> List[Dict]:
        """
        取得所有啟用的訂閱者。
        
        Returns:
            List[Dict]: 訂閱者資料列表
        """
        try:
            response = self.client.table("subscribers").select("*").eq(
                "is_active", True
            ).execute()
            
            logger.info(f"取得 {len(response.data)} 個啟用的訂閱者")
            return response.data
        except Exception as e:
            logger.error(f"取得訂閱者失敗: {e}")
            raise
    
    def article_exists(self, doi: str) -> bool:
        """
        檢查文章是否已存在於資料庫中。
        
        Args:
            doi: 文章的 DOI
        
        Returns:
            bool: 文章存在返回 True，否則返回 False
        """
        try:
            response = self.client.table("articles").select("id").eq(
                "doi", doi
            ).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"檢查文章存在性失敗 (DOI: {doi}): {e}")
            return False
    
    def insert_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        批量插入新文章到資料庫。
        
        Args:
            articles: 文章資料列表，每個包含 journal_id, title, doi, url, 
                     published_date, authors, abstract, category
        
        Returns:
            List[Dict]: 插入成功的文章資料（包含資料庫生成的 ID）
        """
        if not articles:
            return []
        
        try:
            # 準備插入資料
            insert_data = []
            for article in articles:
                insert_data.append({
                    "journal_id": article["journal_id"],
                    "title": article["title"],
                    "doi": article["doi"],
                    "url": article["url"],
                    "published_date": article.get("published_date"),
                    "authors": article.get("authors"),
                    "abstract": article.get("abstract"),
                    "category": article["category"],
                    "discovered_at": datetime.now().isoformat()
                })
            
            # 批量插入
            response = self.client.table("articles").insert(insert_data).execute()
            
            logger.info(f"成功插入 {len(response.data)} 篇文章")
            return response.data
        except Exception as e:
            logger.error(f"插入文章失敗: {e}")
            raise
    
    def get_recent_articles(self, days: int = 1) -> List[Dict]:
        """
        取得最近 N 天發現的文章（包含期刊名稱）。
        
        Args:
            days: 天數
        
        Returns:
            List[Dict]: 文章資料列表（每篇文章包含 journal_name）
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 使用 join 來獲取期刊名稱
            response = self.client.table("articles").select(
                "*, journals(name)"
            ).gte(
                "discovered_at", cutoff_date
            ).execute()
            
            # 展平 journals 資料，將 journals.name 提取為 journal_name
            articles = []
            for article in response.data:
                article_dict = dict(article)
                if 'journals' in article_dict and article_dict['journals']:
                    article_dict['journal_name'] = article_dict['journals']['name']
                    del article_dict['journals']
                else:
                    article_dict['journal_name'] = 'Unknown Journal'
                articles.append(article_dict)
            
            logger.info(f"取得最近 {days} 天的 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"取得最近文章失敗: {e}")
            raise
    
    def insert_notification(
        self, 
        article_id: str, 
        subscriber_id: str, 
        status: str = "success",
        error_message: Optional[str] = None
    ) -> None:
        """
        記錄通知發送狀態。
        
        Args:
            article_id: 文章 ID
            subscriber_id: 訂閱者 ID
            status: 發送狀態 ('success' 或 'failed')
            error_message: 錯誤訊息（如果失敗）
        """
        try:
            notification_data = {
                "article_id": article_id,
                "subscriber_id": subscriber_id,
                "status": status,
                "error_message": error_message,
                "sent_at": datetime.now().isoformat()
            }
            
            self.client.table("notifications").insert(notification_data).execute()
            logger.debug(f"記錄通知狀態: {status}")
        except Exception as e:
            logger.error(f"記錄通知失敗: {e}")
    
    def cleanup_old_data(
        self, 
        max_articles: int = 100, 
        max_notifications: int = 500,
        days_to_keep: int = 90
    ) -> Dict[str, int]:
        """
        清理舊資料，避免資料庫無限增長。
        
        策略：
        1. 文章表（articles）：
           - 優先按數量限制：只保留最新的 max_articles 筆
           - 如果文章數少於 max_articles，則保留 days_to_keep 天內的所有文章
        
        2. 通知記錄表（notifications）：
           - 只保留最近 max_notifications 筆記錄
           - 或保留 days_to_keep 天內的記錄
        
        Args:
            max_articles: 最多保留的文章數量（預設 100）
            max_notifications: 最多保留的通知記錄數量（預設 500）
            days_to_keep: 保留天數（預設 90 天）
        
        Returns:
            Dict[str, int]: 清理結果 {'articles_deleted': N, 'notifications_deleted': M}
        """
        result = {
            'articles_deleted': 0,
            'notifications_deleted': 0
        }
        
        try:
            # ===== 1. 清理文章表 =====
            logger.info(f"開始清理文章表（保留最新 {max_articles} 筆或 {days_to_keep} 天內）")
            
            # 取得文章總數
            count_response = self.client.table("articles").select(
                "id", count="exact"
            ).execute()
            
            total_articles = count_response.count if hasattr(count_response, 'count') else len(count_response.data)
            logger.info(f"  目前文章總數: {total_articles}")
            
            if total_articles > max_articles:
                # 取得要保留的文章 ID（最新的 max_articles 筆）
                keep_response = self.client.table("articles").select("id").order(
                    "discovered_at", desc=True
                ).limit(max_articles).execute()
                
                keep_ids = [article['id'] for article in keep_response.data]
                
                # 刪除不在保留清單中的文章
                if keep_ids:
                    # 使用 not.in 運算符
                    delete_response = self.client.table("articles").delete().not_(
                        "id", "in", f"({','.join(keep_ids)})"
                    ).execute()
                    
                    deleted_count = len(delete_response.data) if delete_response.data else 0
                    result['articles_deleted'] = deleted_count
                    logger.info(f"  ✓ 刪除了 {deleted_count} 篇舊文章（保留最新 {max_articles} 篇）")
            else:
                # 如果文章數少於 max_articles，則按時間刪除
                cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
                delete_response = self.client.table("articles").delete().lt(
                    "discovered_at", cutoff_date
                ).execute()
                
                deleted_count = len(delete_response.data) if delete_response.data else 0
                result['articles_deleted'] = deleted_count
                if deleted_count > 0:
                    logger.info(f"  ✓ 刪除了 {deleted_count} 篇超過 {days_to_keep} 天的舊文章")
                else:
                    logger.info(f"  ✓ 沒有需要刪除的舊文章")
            
            # ===== 2. 清理通知記錄表 =====
            logger.info(f"開始清理通知記錄表（保留最新 {max_notifications} 筆）")
            
            # 取得通知記錄總數
            count_response = self.client.table("notifications").select(
                "id", count="exact"
            ).execute()
            
            total_notifications = count_response.count if hasattr(count_response, 'count') else len(count_response.data)
            logger.info(f"  目前通知記錄總數: {total_notifications}")
            
            if total_notifications > max_notifications:
                # 取得要保留的通知記錄 ID（最新的 max_notifications 筆）
                keep_response = self.client.table("notifications").select("id").order(
                    "sent_at", desc=True
                ).limit(max_notifications).execute()
                
                keep_ids = [notification['id'] for notification in keep_response.data]
                
                # 刪除不在保留清單中的通知記錄
                if keep_ids:
                    delete_response = self.client.table("notifications").delete().not_(
                        "id", "in", f"({','.join(keep_ids)})"
                    ).execute()
                    
                    deleted_count = len(delete_response.data) if delete_response.data else 0
                    result['notifications_deleted'] = deleted_count
                    logger.info(f"  ✓ 刪除了 {deleted_count} 筆舊通知記錄（保留最新 {max_notifications} 筆）")
            else:
                logger.info(f"  ✓ 通知記錄數量在限制內，無需清理")
            
            # 總結
            logger.info(f"資料清理完成：刪除 {result['articles_deleted']} 篇文章、{result['notifications_deleted']} 筆通知記錄")
            return result
            
        except Exception as e:
            logger.error(f"清理資料失敗: {e}")
            raise
    
    def get_database_stats(self) -> Dict[str, int]:
        """
        取得資料庫統計資訊。
        
        Returns:
            Dict[str, int]: 各表的資料筆數
        """
        try:
            stats = {}
            
            # 統計各表資料量
            tables = ['journals', 'subscribers', 'articles', 'notifications']
            
            for table in tables:
                response = self.client.table(table).select("id", count="exact").execute()
                count = response.count if hasattr(response, 'count') else len(response.data)
                stats[table] = count
            
            logger.info(f"資料庫統計: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"取得資料庫統計失敗: {e}")
            return {}