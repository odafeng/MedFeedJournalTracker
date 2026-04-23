"""PubMed E-utilities scraper for fetching journal articles."""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from .base_scraper import BaseScraper

logger = logging.getLogger("journal_tracker")


class PubMedScraper(BaseScraper):
    """
    PubMed E-utilities 爬蟲，使用官方 API 抓取期刊文章。
    
    優勢：
    - 完全合法且免費
    - 包含大部分醫學期刊（包括 Elsevier）
    - 無反爬蟲限制
    - 資料品質高
    """
    
    # PubMed E-utilities API endpoints
    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    # API 限制：每秒最多 3 個請求（無 API key）
    RATE_LIMIT_DELAY = 0.35  # 秒
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 PubMed 爬蟲。
        
        Args:
            api_key: PubMed API key（選用，有 key 可以提高速率限制）
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.last_request_time = 0
    
    def _rate_limit(self):
        """確保遵守 API 速率限制。"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def fetch_articles(
        self, 
        url: str, 
        rss_url: Optional[str] = None, 
        days_back: int = 7,
        journal_issn: Optional[str] = None,
        journal_name: Optional[str] = None
    ) -> List[Dict]:
        """
        使用 PubMed API 抓取期刊文章。
        
        Args:
            url: 期刊網址（未使用，僅為介面相容）
            rss_url: RSS URL（未使用）
            days_back: 抓取幾天前的文章
            journal_issn: 期刊 ISSN（推薦）
            journal_name: 期刊名稱（備用）
        
        Returns:
            List[Dict]: 文章列表
        """
        try:
            logger.info("開始使用 PubMed API 抓取期刊文章")
            
            # 建構搜尋查詢
            query = self._build_query(journal_issn, journal_name, days_back)
            if not query:
                logger.error("無法建構 PubMed 查詢（需要 ISSN 或期刊名稱）")
                return []
            
            logger.info(f"  PubMed 查詢: {query}")
            
            # 步驟 1: 搜尋文章 ID
            pmids = self._search_articles(query)
            if not pmids:
                logger.info("  未找到文章")
                return []
            
            logger.info(f"  找到 {len(pmids)} 篇文章")
            
            # 步驟 2: 獲取文章詳細資訊
            articles = self._fetch_article_details(pmids, days_back)
            
            logger.info(f"成功解析 {len(articles)} 篇文章（過去 {days_back} 天）")
            return articles
            
        except Exception as e:
            logger.error(f"PubMed 抓取失敗: {e}")
            return []
    
    def _build_query(
        self, 
        issn: Optional[str], 
        journal_name: Optional[str], 
        days_back: int
    ) -> Optional[str]:
        """
        建構 PubMed 搜尋查詢。
        
        Args:
            issn: 期刊 ISSN
            journal_name: 期刊名稱
            days_back: 天數
        
        Returns:
            Optional[str]: PubMed 查詢字串
        """
        # 優先使用 ISSN（更精確）
        if issn:
            journal_query = f'"{issn}"[ISSN]'
        elif journal_name:
            journal_query = f'"{journal_name}"[Journal]'
        else:
            return None
        
        # 加上日期範圍
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        date_query = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
        
        return f"{journal_query} AND {date_query}"
    
    def _search_articles(self, query: str, max_results: int = 100) -> List[str]:
        """
        使用 ESearch 搜尋文章，返回 PMID 列表。
        
        Args:
            query: PubMed 查詢字串
            max_results: 最多返回結果數
        
        Returns:
            List[str]: PMID 列表
        """
        try:
            self._rate_limit()
            
            params = {
                'db': 'pubmed',
                'term': query,
                'retmax': max_results,
                'retmode': 'xml',
                'sort': 'pub_date',
                'datetype': 'pdat'
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(
                self.ESEARCH_URL, 
                params=params, 
                timeout=30
            )
            response.raise_for_status()
            
            # 解析 XML
            root = ET.fromstring(response.content)
            
            # 提取 PMIDs
            pmids = []
            for id_elem in root.findall('.//Id'):
                if id_elem.text:
                    pmids.append(id_elem.text)
            
            return pmids
            
        except Exception as e:
            logger.error(f"PubMed 搜尋失敗: {e}")
            return []
    
    def _fetch_article_details(
        self, 
        pmids: List[str], 
        days_back: int
    ) -> List[Dict]:
        """
        使用 EFetch 獲取文章詳細資訊。
        
        Args:
            pmids: PMID 列表
            days_back: 天數（用於過濾）
        
        Returns:
            List[Dict]: 文章列表
        """
        if not pmids:
            return []
        
        try:
            self._rate_limit()
            
            # 批量獲取（最多 200 個）
            pmid_str = ','.join(pmids[:200])
            
            params = {
                'db': 'pubmed',
                'id': pmid_str,
                'retmode': 'xml',
                'rettype': 'abstract'
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(
                self.EFETCH_URL, 
                params=params, 
                timeout=60
            )
            response.raise_for_status()
            
            # 解析 XML
            root = ET.fromstring(response.content)
            
            # 提取文章資訊
            articles = []
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            for article_elem in root.findall('.//PubmedArticle'):
                try:
                    article = self._parse_article(article_elem)
                    if article:
                        # 檢查日期
                        if article.get('published_date'):
                            pub_date = datetime.strptime(
                                article['published_date'], 
                                '%Y-%m-%d'
                            )
                            if pub_date >= cutoff_date:
                                articles.append(article)
                        else:
                            # 沒有日期的也保留（可能是最新的）
                            articles.append(article)
                except Exception as e:
                    logger.debug(f"解析文章失敗: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"PubMed 獲取詳細資訊失敗: {e}")
            return []
    
    def _parse_article(self, article_elem: ET.Element) -> Optional[Dict]:
        """
        解析單篇文章的 XML。
        
        Args:
            article_elem: PubmedArticle XML 元素
        
        Returns:
            Optional[Dict]: 文章資料
        """
        try:
            medline = article_elem.find('.//MedlineCitation')
            article_node = medline.find('.//Article')
            
            if article_node is None:
                return None
            
            # 標題
            title_elem = article_node.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else None
            
            if not title:
                return None
            
            # 取得 PMID（一定存在）
            pmid_elem = medline.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            if not pmid:
                logger.debug("找不到 PMID，跳過文章")
                return None
            
            # DOI（在 PubmedData/ArticleIdList 中）
            doi = None
            pubmed_data = article_elem.find('.//PubmedData')
            if pubmed_data is not None:
                for id_elem in pubmed_data.findall('.//ArticleId'):
                    if id_elem.get('IdType') == 'doi' and id_elem.text:
                        doi = self.clean_doi(id_elem.text)
                        break
            
            # 如果沒有 DOI，使用 PMID 作為唯一識別碼
            if not doi:
                doi = f"PMID:{pmid}"
            
            # 確保 doi 不是 None
            if not doi:
                logger.debug(f"無法取得 DOI/PMID: {title[:50]}")
                return None
            
            # 發表日期
            pub_date = self._extract_pub_date(article_node)
            
            # 作者
            authors = self._extract_authors(article_node)
            
            # 摘要
            abstract = self._extract_abstract(article_node)
            
            # URL（使用 PMID 或 DOI 建構）
            if pmid:
                article_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif doi and not doi.startswith('PMID:'):
                article_url = f"https://doi.org/{doi}"
            else:
                article_url = "https://pubmed.ncbi.nlm.nih.gov/"
            
            return {
                'title': title.strip(),
                'doi': doi,
                'url': article_url,
                'published_date': pub_date,
                'authors': authors,
                'abstract': abstract
            }
            
        except Exception as e:
            logger.debug(f"解析文章元素失敗: {e}")
            return None
    
    def _extract_pub_date(self, article_node: ET.Element) -> Optional[str]:
        """提取發表日期。"""
        # 嘗試 PubDate
        pub_date_elem = article_node.find('.//PubDate')
        if pub_date_elem is not None:
            year = pub_date_elem.find('Year')
            month = pub_date_elem.find('Month')
            day = pub_date_elem.find('Day')
            
            if year is not None:
                year_str = year.text
                month_str = month.text if month is not None else '01'
                day_str = day.text if day is not None else '01'
                
                # 轉換月份名稱
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                
                if month_str in month_map:
                    month_str = month_map[month_str]
                
                try:
                    date_obj = datetime.strptime(
                        f"{year_str}-{month_str}-{day_str}", 
                        '%Y-%m-%d'
                    )
                    return date_obj.strftime('%Y-%m-%d')
                except Exception:
                    pass
        
        return None
    
    def _extract_authors(self, article_node: ET.Element) -> Optional[str]:
        """提取作者列表。"""
        authors_list = []
        
        author_list_elem = article_node.find('.//AuthorList')
        if author_list_elem is not None:
            for author_elem in author_list_elem.findall('.//Author'):
                last_name = author_elem.find('LastName')
                fore_name = author_elem.find('ForeName')
                
                if last_name is not None:
                    name = last_name.text
                    if fore_name is not None:
                        name = f"{fore_name.text} {name}"
                    authors_list.append(name)
        
        if authors_list:
            # 限制作者數量
            if len(authors_list) > 10:
                authors_str = ', '.join(authors_list[:10]) + ' et al.'
            else:
                authors_str = ', '.join(authors_list)
            return self.truncate_text(authors_str, 500)
        
        return None
    
    def _extract_abstract(self, article_node: ET.Element) -> Optional[str]:
        """提取摘要。"""
        abstract_elem = article_node.find('.//Abstract')
        if abstract_elem is not None:
            abstract_texts = []
            for text_elem in abstract_elem.findall('.//AbstractText'):
                if text_elem.text:
                    abstract_texts.append(text_elem.text)
            
            if abstract_texts:
                abstract = ' '.join(abstract_texts)
                return self.truncate_text(abstract, 1000)
        
        return None

