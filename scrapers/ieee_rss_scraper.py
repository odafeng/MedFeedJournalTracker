"""Special RSS scraper for IEEE journals that require browser-like requests."""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from .base_scraper import BaseScraper

logger = logging.getLogger("journal_tracker")


class IEEERSSScraper(BaseScraper):
    """IEEE 期刊專用的 RSS 爬蟲，使用完整的瀏覽器模擬。"""
    
    def __init__(self):
        """初始化 IEEE RSS 爬蟲，設定完整的瀏覽器 headers。"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://ieeexplore.ieee.org/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'max-age=0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_articles(
        self, 
        url: str, 
        rss_url: Optional[str] = None, 
        days_back: int = 7
    ) -> List[Dict]:
        """
        抓取 IEEE RSS feed 文章。
        
        Args:
            url: 期刊網址
            rss_url: RSS feed 網址
            days_back: 抓取幾天前的文章
        
        Returns:
            List[Dict]: 文章列表
        """
        if not rss_url:
            logger.warning(f"沒有提供 RSS URL: {url}")
            return []
        
        try:
            logger.info(f"開始抓取 IEEE RSS feed: {rss_url}")
            
            # 先訪問期刊主頁建立 session（可能需要 cookies）
            try:
                self.session.get(url, timeout=10)
                logger.debug("已訪問期刊主頁建立 session")
            except:
                pass
            
            # 下載 RSS feed
            response = self.session.get(rss_url, timeout=15)
            
            if response.status_code == 418:
                logger.error(f"IEEE 封鎖了請求 (HTTP 418)，RSS URL: {rss_url}")
                logger.info("建議：手動在瀏覽器中訂閱 RSS，或使用 IEEE Xplore API")
                return []
            
            response.raise_for_status()
            
            # 解析 XML
            root = ET.fromstring(response.content)
            
            # 計算截止日期
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            articles = []
            
            # 找到所有 item 元素
            items = root.findall('.//item')
            
            if not items:
                logger.warning(f"RSS feed 中沒有找到 item 元素: {rss_url}")
                return []
            
            logger.info(f"找到 {len(items)} 個 RSS items")
            
            for item in items:
                try:
                    article = self._parse_item(item, cutoff_date)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"解析 item 失敗: {e}")
                    continue
            
            logger.info(f"成功解析 {len(articles)} 篇文章（過去 {days_back} 天）")
            return articles
            
        except requests.RequestException as e:
            logger.error(f"請求失敗 ({rss_url}): {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"XML 解析失敗 ({rss_url}): {e}")
            return []
        except Exception as e:
            logger.error(f"未知錯誤 ({rss_url}): {e}")
            return []
    
    def _parse_item(self, item: ET.Element, cutoff_date: datetime) -> Optional[Dict]:
        """
        解析單一 RSS item。
        
        Args:
            item: XML Element
            cutoff_date: 截止日期
        
        Returns:
            Optional[Dict]: 文章資料
        """
        # 提取標題
        title_elem = item.find('title')
        title = title_elem.text if title_elem is not None else None
        
        if not title:
            return None
        
        # 提取連結
        link_elem = item.find('link')
        article_url = link_elem.text if link_elem is not None else None
        
        # 提取發表日期
        pubdate_elem = item.find('pubDate')
        published_date = None
        
        if pubdate_elem is not None:
            date_str = self.parse_date(pubdate_elem.text)
            if date_str:
                try:
                    published_date = datetime.strptime(date_str, '%Y-%m-%d')
                except:
                    pass
        
        # 如果沒有日期，使用當前時間
        if not published_date:
            published_date = datetime.now()
        
        # 檢查日期範圍
        if published_date < cutoff_date:
            return None
        
        # 提取 DOI
        doi = self._extract_doi_from_item(item, article_url)
        
        if not doi:
            logger.debug(f"無法提取 DOI: {title[:50]}")
            return None
        
        # 提取作者
        authors = self._extract_authors_from_item(item)
        
        # 提取摘要
        abstract = self._extract_abstract_from_item(item)
        
        return {
            'title': title.strip(),
            'doi': doi,
            'url': article_url or f"https://doi.org/{doi}",
            'published_date': published_date.strftime('%Y-%m-%d'),
            'authors': authors,
            'abstract': abstract
        }
    
    def _extract_doi_from_item(self, item: ET.Element, url: Optional[str]) -> Optional[str]:
        """從 item 中提取 DOI。"""
        # 方法 1: 從 description 或其他欄位尋找直接的 DOI
        desc_elem = item.find('description')
        if desc_elem is not None and desc_elem.text:
            doi_match = re.search(r'10\.\d{4,}/[^\s<&]+', desc_elem.text)
            if doi_match:
                return self.clean_doi(doi_match.group(0))
        
        # 方法 2: 從 URL 尋找 DOI
        if url:
            doi_match = re.search(r'10\.\d{4,}/[^\s&]+', url)
            if doi_match:
                return self.clean_doi(doi_match.group(0))
        
        # 方法 3: 從 dc:identifier
        identifier_elem = item.find('.//{http://purl.org/dc/elements/1.1/}identifier')
        if identifier_elem is not None and identifier_elem.text:
            return self.clean_doi(identifier_elem.text)
        
        # 方法 4: IEEE 特殊處理 - 從 document ID 構造 DOI
        # IEEE RSS 通常只提供 document URL，格式為：
        # http://ieeexplore.ieee.org/document/[DOCUMENT_ID]
        if url:
            doc_id_match = re.search(r'/document/(\d+)', url)
            if doc_id_match:
                document_id = doc_id_match.group(1)
                # IEEE DOI 格式通常是：10.1109/DOCUMENT_ID
                # 這是一個簡化版，實際上不同期刊可能有不同的前綴
                doi = f"10.1109/{document_id}"
                logger.debug(f"從 document ID 構造 DOI: {doi}")
                return doi
        
        return None
    
    def _extract_authors_from_item(self, item: ET.Element) -> Optional[str]:
        """從 item 中提取作者。"""
        # 嘗試 dc:creator
        creator_elem = item.find('.//{http://purl.org/dc/elements/1.1/}creator')
        if creator_elem is not None and creator_elem.text:
            return self.truncate_text(creator_elem.text, 500)
        
        # 嘗試 author
        author_elem = item.find('author')
        if author_elem is not None and author_elem.text:
            return self.truncate_text(author_elem.text, 500)
        
        return None
    
    def _extract_abstract_from_item(self, item: ET.Element) -> Optional[str]:
        """從 item 中提取摘要。"""
        desc_elem = item.find('description')
        if desc_elem is not None and desc_elem.text:
            # 移除 HTML 標籤
            text = re.sub(r'<[^>]+>', '', desc_elem.text)
            return self.truncate_text(text, 1000)
        
        return None
