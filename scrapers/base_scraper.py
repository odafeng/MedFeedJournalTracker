"""Base scraper abstract class for journal article fetching."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import re
import logging

logger = logging.getLogger("journal_tracker")


class BaseScraper(ABC):
    """爬蟲抽象基類，定義所有爬蟲的共同介面。"""
    
    @abstractmethod
    def fetch_articles(
        self, 
        url: str, 
        rss_url: Optional[str] = None, 
        days_back: int = 7
    ) -> List[Dict]:
        """
        抓取文章。
        
        Args:
            url: 期刊網址
            rss_url: RSS feed 網址（如果有）
            days_back: 抓取幾天前的文章
        
        Returns:
            List[Dict]: 文章列表，每個文章包含:
                - title: str - 文章標題
                - doi: str - DOI（已清理）
                - url: str - 文章網址
                - published_date: str - 發表日期 (YYYY-MM-DD)
                - authors: str (optional) - 作者列表
                - abstract: str (optional) - 摘要
        """
        pass
    
    def clean_doi(self, doi: str) -> Optional[str]:
        """
        清理和標準化 DOI 或 PMID。
        
        Args:
            doi: 原始 DOI/PMID 字串
        
        Returns:
            Optional[str]: 清理後的 DOI/PMID，如果無效則返回 None
        
        Examples:
            >>> scraper.clean_doi('https://doi.org/10.1109/TMI.2025.12345')
            '10.1109/TMI.2025.12345'
            >>> scraper.clean_doi('DOI: 10.1038/s41586-025-00001-1')
            '10.1038/s41586-025-00001-1'
            >>> scraper.clean_doi('PMID:12345678')
            'PMID:12345678'
        """
        if not doi:
            return None
        
        # 移除空白
        doi = doi.strip()
        
        # 優先檢查是否為 PMID 格式（在做任何 replace 之前）
        if doi.startswith('PMID:'):
            # PMID 格式有效，直接返回
            return doi
        
        # 移除常見的 DOI 前綴
        doi = doi.replace('https://doi.org/', '')
        doi = doi.replace('http://doi.org/', '')
        doi = doi.replace('https://dx.doi.org/', '')
        doi = doi.replace('http://dx.doi.org/', '')
        doi = doi.replace('DOI:', '')
        doi = doi.replace('doi:', '')
        
        # 再次移除空白
        doi = doi.strip()
        
        # 驗證 DOI 格式 (應該以 10. 開頭)
        if not doi.startswith('10.'):
            # 嘗試從字串中提取 DOI
            doi_match = re.search(r'10\.\d{4,}[^\s]*', doi)
            if doi_match:
                doi = doi_match.group(0)
            else:
                logger.debug(f"無標準 DOI 格式: {doi}")
                return None
        
        return doi
    
    def parse_date(self, date_str: str) -> Optional[str]:
        """
        解析並標準化日期格式為 YYYY-MM-DD。
        
        Args:
            date_str: 原始日期字串
        
        Returns:
            Optional[str]: 標準化的日期字串 (YYYY-MM-DD)，失敗則返回 None
        """
        if not date_str:
            return None
        
        # 常見的日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d %b %Y',  # 01 Jan 2025
            '%d %B %Y',  # 01 January 2025
            '%B %d, %Y',  # January 01, 2025
            '%Y-%m-%dT%H:%M:%S',  # ISO 8601
            '%Y-%m-%dT%H:%M:%SZ',
            '%a, %d %b %Y %H:%M:%S %Z',  # RSS format with timezone name
            '%a, %d %b %Y %H:%M:%S %z',  # RSS format with timezone offset
            '%A, %d %B %Y %H:%M:%S %Z',  # Full day/month names
            '%A, %d %B %Y %H:%M:%S %z',
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        logger.warning(f"無法解析日期: {date_str}")
        return None
    
    def truncate_text(self, text: str, max_length: int = 500) -> str:
        """
        截斷文字到指定長度。
        
        Args:
            text: 原始文字
            max_length: 最大長度
        
        Returns:
            str: 截斷後的文字
        """
        if not text:
            return ""
        
        text = text.strip()
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "..."
