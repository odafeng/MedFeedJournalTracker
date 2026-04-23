"""RSS scraper for fetching journal articles from RSS feeds."""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import feedparser

from .base_scraper import BaseScraper

logger = logging.getLogger("journal_tracker")


class RSSScraper(BaseScraper):
    """通用 RSS 爬蟲，適用於大部分提供 RSS feed 的期刊。"""
    
    def __init__(self):
        """初始化 RSS 爬蟲，設定自訂 headers 避免被封鎖。"""
        # 設定真實的瀏覽器 User-Agent
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    
    def fetch_articles(
        self, 
        url: str, 
        rss_url: Optional[str] = None, 
        days_back: int = 7
    ) -> List[Dict]:
        """
        使用 feedparser 解析 RSS feed 並抓取文章。
        
        Args:
            url: 期刊網址（備用）
            rss_url: RSS feed 網址
            days_back: 抓取幾天前的文章
        
        Returns:
            List[Dict]: 文章列表
        """
        if not rss_url:
            logger.warning(f"沒有提供 RSS URL: {url}")
            return []
        
        try:
            logger.info(f"開始解析 RSS feed: {rss_url}")
            
            # 解析 RSS feed，使用自訂 User-Agent
            feed = feedparser.parse(rss_url, agent=self.user_agent)
            
            # 即使有 bozo 標記（格式警告），也嘗試解析
            if feed.bozo:
                logger.warning(f"RSS feed 格式警告: {rss_url}")
                # 如果有嚴重錯誤且沒有任何條目，才放棄
                if not feed.entries and hasattr(feed, 'bozo_exception'):
                    logger.error(f"RSS feed 解析失敗: {feed.bozo_exception}")
                    return []
            
            if not feed.entries:
                logger.warning(f"RSS feed 沒有文章: {rss_url}")
                return []
            
            # 計算截止日期
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            articles = []
            for entry in feed.entries:
                try:
                    article = self._parse_entry(entry, cutoff_date)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"解析文章失敗: {e}")
                    continue
            
            logger.info(f"成功解析 {len(articles)} 篇文章（過去 {days_back} 天）")
            return articles
            
        except Exception as e:
            logger.error(f"RSS feed 解析失敗 ({rss_url}): {e}")
            return []
    
    def _parse_entry(self, entry, cutoff_date: datetime) -> Optional[Dict]:
        """
        解析單一 RSS entry。
        
        Args:
            entry: feedparser entry 物件
            cutoff_date: 截止日期
        
        Returns:
            Optional[Dict]: 文章資料，如果不符合條件則返回 None
        """
        # 提取發表日期
        published_date = self._extract_date(entry)
        if not published_date:
            logger.debug(f"無法提取日期，跳過文章: {entry.get('title', 'Unknown')}")
            return None
        
        # 檢查日期是否在範圍內
        if published_date < cutoff_date:
            return None
        
        # 提取 DOI
        doi = self._extract_doi(entry)
        if not doi:
            logger.debug(f"無法提取 DOI，跳過文章: {entry.get('title', 'Unknown')}")
            return None
        
        # 提取標題
        title = entry.get('title', '').strip()
        if not title:
            logger.debug(f"沒有標題，跳過文章: DOI {doi}")
            return None
        
        # 提取網址
        article_url = entry.get('link', '')
        if not article_url:
            article_url = f"https://doi.org/{doi}"
        
        # 提取作者
        authors = self._extract_authors(entry)
        
        # 提取摘要
        abstract = self._extract_abstract(entry)
        
        article = {
            'title': title,
            'doi': doi,
            'url': article_url,
            'published_date': published_date.strftime('%Y-%m-%d'),
            'authors': authors,
            'abstract': abstract
        }
        
        logger.debug(f"成功解析文章: {title[:50]}...")
        return article
    
    def _extract_date(self, entry) -> Optional[datetime]:
        """從 entry 中提取發表日期。"""
        # 嘗試不同的日期欄位
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except Exception:
                        pass
        
        # 嘗試字串格式
        date_str_fields = ['published', 'updated', 'created']
        for field in date_str_fields:
            date_str = entry.get(field, '')
            if date_str:
                parsed = self.parse_date(date_str)
                if parsed:
                    try:
                        return datetime.strptime(parsed, '%Y-%m-%d')
                    except Exception:
                        pass
        
        return None
    
    def _extract_doi(self, entry) -> Optional[str]:
        """從 entry 中提取 DOI。"""
        # 方法 1: 從 prism:doi 欄位
        doi = entry.get('prism_doi', '') or entry.get('dc_identifier', '')
        if doi:
            return self.clean_doi(doi)
        
        # 方法 2: 從 link 中提取
        link = entry.get('link', '')
        if 'doi.org' in link:
            doi_match = re.search(r'10\.\d{4,}/[^\s&]+', link)
            if doi_match:
                return self.clean_doi(doi_match.group(0))
        
        # 方法 3: 從 id 欄位
        entry_id = entry.get('id', '')
        if entry_id:
            doi_match = re.search(r'10\.\d{4,}/[^\s&]+', entry_id)
            if doi_match:
                return self.clean_doi(doi_match.group(0))
        
        # 方法 4: 從 summary/description 中提取
        summary = entry.get('summary', '') + entry.get('description', '')
        if summary:
            doi_match = re.search(r'(?:doi:|DOI:)?\s*(10\.\d{4,}/[^\s<&]+)', summary)
            if doi_match:
                return self.clean_doi(doi_match.group(1))
        
        return None
    
    def _extract_authors(self, entry) -> Optional[str]:
        """從 entry 中提取作者列表。"""
        authors_list = []
        
        # 方法 1: 從 authors 欄位
        if hasattr(entry, 'authors') and entry.authors:
            for author in entry.authors:
                name = author.get('name', '')
                if name:
                    authors_list.append(name)
        
        # 方法 2: 從 author 欄位
        elif hasattr(entry, 'author') and entry.author:
            authors_list.append(entry.author)
        
        # 方法 3: 從 dc:creator
        elif 'dc_creator' in entry:
            authors_list.append(entry.dc_creator)
        
        if authors_list:
            # 限制作者數量，避免太長
            if len(authors_list) > 10:
                authors_str = ', '.join(authors_list[:10]) + ' et al.'
            else:
                authors_str = ', '.join(authors_list)
            return self.truncate_text(authors_str, 500)
        
        return None
    
    def _extract_abstract(self, entry) -> Optional[str]:
        """從 entry 中提取摘要。"""
        # 嘗試不同的摘要欄位
        abstract = entry.get('summary', '') or entry.get('description', '') or entry.get('content', '')
        
        if isinstance(abstract, list) and abstract:
            abstract = abstract[0].get('value', '')
        
        if abstract:
            # 移除 HTML 標籤
            abstract = re.sub(r'<[^>]+>', '', abstract)
            # 移除多餘空白
            abstract = re.sub(r'\s+', ' ', abstract).strip()
            # 截斷長度
            return self.truncate_text(abstract, 1000)
        
        return None
