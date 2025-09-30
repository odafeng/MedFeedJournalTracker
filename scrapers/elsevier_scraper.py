"""Elsevier/ScienceDirect scraper for journals without RSS feeds."""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time
import re

from .base_scraper import BaseScraper

logger = logging.getLogger("journal_tracker")


class ElsevierScraper(BaseScraper):
    """Elsevier/ScienceDirect 期刊爬蟲，用於沒有 RSS feed 的期刊。"""
    
    def __init__(self):
        """初始化爬蟲，設定 headers 避免被封鎖。"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def fetch_articles(
        self, 
        url: str, 
        rss_url: Optional[str] = None, 
        days_back: int = 7
    ) -> List[Dict]:
        """
        爬取 ScienceDirect 最新文章。
        
        Args:
            url: ScienceDirect 期刊網址
            rss_url: 未使用
            days_back: 抓取幾天前的文章
        
        Returns:
            List[Dict]: 文章列表
        """
        try:
            logger.info(f"開始爬取 Elsevier 期刊: {url}")
            
            # 發送請求
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 計算截止日期
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # 查找文章列表
            articles = self._parse_article_list(soup, cutoff_date, url)
            
            logger.info(f"成功爬取 {len(articles)} 篇文章")
            return articles
            
        except requests.RequestException as e:
            logger.error(f"網頁請求失敗 ({url}): {e}")
            return []
        except Exception as e:
            logger.error(f"爬取失敗 ({url}): {e}")
            return []
    
    def _parse_article_list(
        self, 
        soup: BeautifulSoup, 
        cutoff_date: datetime,
        base_url: str
    ) -> List[Dict]:
        """
        解析文章列表。
        
        Args:
            soup: BeautifulSoup 物件
            cutoff_date: 截止日期
            base_url: 基礎 URL
        
        Returns:
            List[Dict]: 文章列表
        """
        articles = []
        
        # ScienceDirect 的文章通常在特定的 class 中
        # 這個選擇器可能需要根據實際網頁結構調整
        article_elements = soup.find_all('li', class_='js-article')
        
        if not article_elements:
            # 嘗試其他可能的選擇器
            article_elements = soup.find_all('article')
        
        if not article_elements:
            logger.warning("未找到文章元素，可能網頁結構已改變")
            return articles
        
        for element in article_elements:
            try:
                article = self._parse_article_element(element, cutoff_date, base_url)
                if article:
                    articles.append(article)
                    # 避免請求太快
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"解析文章元素失敗: {e}")
                continue
        
        return articles
    
    def _parse_article_element(
        self, 
        element, 
        cutoff_date: datetime,
        base_url: str
    ) -> Optional[Dict]:
        """
        解析單一文章元素。
        
        Args:
            element: BeautifulSoup 元素
            cutoff_date: 截止日期
            base_url: 基礎 URL
        
        Returns:
            Optional[Dict]: 文章資料
        """
        # 提取標題
        title_elem = element.find('a', class_='anchor article-content-title')
        if not title_elem:
            title_elem = element.find('h3') or element.find('h2')
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        
        # 提取 URL
        article_url = title_elem.get('href', '')
        if article_url and not article_url.startswith('http'):
            article_url = 'https://www.sciencedirect.com' + article_url
        
        # 提取 DOI
        doi = self._extract_doi_from_url(article_url)
        if not doi:
            # 嘗試從元素中尋找 DOI
            doi_elem = element.find('a', href=re.compile(r'doi\.org'))
            if doi_elem:
                doi = self.clean_doi(doi_elem.get('href', ''))
        
        if not doi:
            logger.debug(f"無法提取 DOI: {title[:50]}")
            return None
        
        # 提取發表日期
        date_elem = element.find('span', class_='article-info-date')
        if not date_elem:
            date_elem = element.find(text=re.compile(r'\d{4}'))
        
        published_date = None
        if date_elem:
            date_str = date_elem.get_text(strip=True) if hasattr(date_elem, 'get_text') else str(date_elem)
            published_date_str = self.parse_date(date_str)
            if published_date_str:
                try:
                    published_date = datetime.strptime(published_date_str, '%Y-%m-%d')
                except:
                    pass
        
        # 如果沒有日期或日期太舊，跳過
        if not published_date:
            logger.debug(f"無法提取日期或日期太舊: {title[:50]}")
            # 對於沒有日期的文章，我們仍然保留（可能是最新的）
            published_date = datetime.now()
        
        if published_date < cutoff_date:
            return None
        
        # 提取作者
        authors = self._extract_authors_from_element(element)
        
        # 提取摘要（通常需要訪問文章頁面）
        abstract = self._extract_abstract_from_element(element)
        
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
    
    def _extract_doi_from_url(self, url: str) -> Optional[str]:
        """從 URL 中提取 DOI。"""
        if not url:
            return None
        
        # ScienceDirect URL 格式通常包含 pii 或 doi
        # 例如: https://www.sciencedirect.com/science/article/pii/S1532046421001234
        
        # 嘗試從 URL 提取
        doi_match = re.search(r'10\.\d{4,}/[^\s&?]+', url)
        if doi_match:
            return self.clean_doi(doi_match.group(0))
        
        # 如果是 pii，我們需要額外的 API 呼叫來取得 DOI
        # 這裡暫時返回 None，實際使用時可能需要 Elsevier API
        pii_match = re.search(r'/pii/([A-Z0-9]+)', url)
        if pii_match:
            pii = pii_match.group(1)
            # 注意: 這裡需要 Elsevier API key 來轉換 PII 到 DOI
            # 暫時使用 PII 作為替代識別碼（不理想但可行）
            logger.warning(f"找到 PII 但無法轉換為 DOI: {pii}")
            # 可以暫時用 PII 當作 DOI 的替代品
            return f"PII:{pii}"
        
        return None
    
    def _extract_authors_from_element(self, element) -> Optional[str]:
        """從元素中提取作者。"""
        authors_elem = element.find('span', class_='authors')
        if not authors_elem:
            authors_elem = element.find('div', class_='authors')
        
        if authors_elem:
            authors_text = authors_elem.get_text(strip=True)
            # 清理格式
            authors_text = re.sub(r'\s+', ' ', authors_text)
            return self.truncate_text(authors_text, 500)
        
        return None
    
    def _extract_abstract_from_element(self, element) -> Optional[str]:
        """從元素中提取摘要。"""
        abstract_elem = element.find('div', class_='abstract')
        if not abstract_elem:
            abstract_elem = element.find('p', class_='abstract')
        
        if abstract_elem:
            abstract_text = abstract_elem.get_text(strip=True)
            # 移除 "Abstract" 前綴
            abstract_text = re.sub(r'^Abstract:?\s*', '', abstract_text, flags=re.IGNORECASE)
            return self.truncate_text(abstract_text, 1000)
        
        return None
