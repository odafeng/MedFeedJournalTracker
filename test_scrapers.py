"""測試爬蟲功能的腳本。"""

import sys
from scrapers.rss_scraper import RSSScraper
from scrapers.elsevier_scraper import ElsevierScraper
from utils.logger import setup_logger

logger = setup_logger("test_scrapers")


def test_rss_scraper():
    """測試 RSS 爬蟲。"""
    logger.info("=" * 60)
    logger.info("測試 RSS 爬蟲")
    logger.info("=" * 60)
    
    scraper = RSSScraper()
    
    # 測試 IEEE TMI
    test_feeds = [
        {
            "name": "IEEE Transactions on Medical Imaging",
            "url": "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=42",
            "rss_url": "https://ieeexplore.ieee.org/rss/TOC42.XML"
        },
        {
            "name": "Nature Machine Intelligence",
            "url": "https://www.nature.com/natmachintell/",
            "rss_url": "https://www.nature.com/natmachintell.rss"
        }
    ]
    
    for feed in test_feeds:
        logger.info(f"\n測試期刊: {feed['name']}")
        logger.info(f"RSS URL: {feed['rss_url']}")
        
        articles = scraper.fetch_articles(
            url=feed['url'],
            rss_url=feed['rss_url'],
            days_back=30  # 抓取 30 天內的文章以確保有結果
        )
        
        logger.info(f"找到 {len(articles)} 篇文章")
        
        if articles:
            logger.info("\n前 3 篇文章:")
            for i, article in enumerate(articles[:3], 1):
                logger.info(f"\n  文章 {i}:")
                logger.info(f"    標題: {article['title'][:80]}...")
                logger.info(f"    DOI: {article['doi']}")
                logger.info(f"    日期: {article['published_date']}")
                logger.info(f"    作者: {article['authors'][:80] if article.get('authors') else 'N/A'}...")
                logger.info(f"    URL: {article['url']}")


def test_elsevier_scraper():
    """測試 Elsevier 爬蟲。"""
    logger.info("\n" + "=" * 60)
    logger.info("測試 Elsevier 爬蟲")
    logger.info("=" * 60)
    
    scraper = ElsevierScraper()
    
    # 測試 Journal of Biomedical Informatics
    journal = {
        "name": "Journal of Biomedical Informatics",
        "url": "https://www.sciencedirect.com/journal/journal-of-biomedical-informatics"
    }
    
    logger.info(f"\n測試期刊: {journal['name']}")
    logger.info(f"URL: {journal['url']}")
    
    articles = scraper.fetch_articles(
        url=journal['url'],
        days_back=30
    )
    
    logger.info(f"找到 {len(articles)} 篇文章")
    
    if articles:
        logger.info("\n前 3 篇文章:")
        for i, article in enumerate(articles[:3], 1):
            logger.info(f"\n  文章 {i}:")
            logger.info(f"    標題: {article['title'][:80]}...")
            logger.info(f"    DOI: {article['doi']}")
            logger.info(f"    日期: {article['published_date']}")
            logger.info(f"    作者: {article['authors'][:80] if article.get('authors') else 'N/A'}...")
            logger.info(f"    URL: {article['url']}")


if __name__ == "__main__":
    try:
        # 測試 RSS 爬蟲
        test_rss_scraper()
        
        # 測試 Elsevier 爬蟲
        test_elsevier_scraper()
        
        logger.info("\n" + "=" * 60)
        logger.info("測試完成！")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("\n測試被使用者中斷")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n測試過程中發生錯誤: {e}", exc_info=True)
        sys.exit(1)
