"""驗證所有期刊的 RSS feed 是否可用。"""

import json
import feedparser
import requests
from utils.logger import setup_logger
from scrapers.rss_scraper import RSSScraper
from scrapers.ieee_rss_scraper import IEEERSSScraper
from scrapers.elsevier_scraper import ElsevierScraper
from scrapers.pubmed_scraper import PubMedScraper

logger = setup_logger("verify_rss")


def verify_journal_with_scraper(journal: dict) -> dict:
    """
    使用實際的 scraper 驗證期刊。
    
    Returns:
        dict: {
            'name': 期刊名稱,
            'rss_url': RSS URL,
            'status': 'success' | 'failed' | 'no_rss',
            'entries_count': 文章數量,
            'error': 錯誤訊息（如果有）
        }
    """
    name = journal['name']
    rss_url = journal.get('rss_url')
    url = journal['url']
    scraper_class = journal.get('scraper_class', 'RSSScraper')
    
    result = {
        'name': name,
        'rss_url': rss_url,
        'scraper_class': scraper_class,
        'status': 'unknown',
        'entries_count': 0,
        'error': None
    }
    
    if not rss_url and scraper_class != 'ElsevierScraper':
        result['status'] = 'no_rss'
        result['error'] = '未提供 RSS URL'
        return result
    
    try:
        logger.info(f"測試: {name}")
        logger.info(f"  使用爬蟲: {scraper_class}")
        if rss_url:
            logger.info(f"  RSS URL: {rss_url}")
        
        # 根據 scraper_class 選擇對應的爬蟲
        if scraper_class == 'IEEERSSScraper':
            scraper = IEEERSSScraper()
        elif scraper_class == 'ElsevierScraper':
            scraper = ElsevierScraper()
        elif scraper_class == 'PubMedScraper':
            # 載入 PubMed API key（如果有）
            import os
            from dotenv import load_dotenv
            env_files = ['.env', '.env.local', '.env.production']
            for env_file in env_files:
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    break
            pubmed_api_key = os.getenv('PUBMED_API_KEY')
            scraper = PubMedScraper(api_key=pubmed_api_key)
        else:
            scraper = RSSScraper()
        
        # 使用爬蟲抓取文章（只抓最近 30 天的，快速測試）
        fetch_kwargs = {'url': url, 'rss_url': rss_url, 'days_back': 30}
        
        # 如果是 PubMedScraper，傳入 ISSN 和期刊名稱
        if scraper_class == 'PubMedScraper':
            fetch_kwargs['journal_issn'] = journal.get('issn')
            fetch_kwargs['journal_name'] = journal.get('name')
        
        articles = scraper.fetch_articles(**fetch_kwargs)
        
        if articles:
            result['status'] = 'success'
            result['entries_count'] = len(articles)
            logger.info(f"  ✅ 成功！找到 {len(articles)} 篇文章")
            
            # 顯示第一篇文章的標題
            if articles:
                first_title = articles[0].get('title', 'N/A')
                logger.info(f"  第一篇: {first_title[:60]}...")
        else:
            result['status'] = 'failed'
            result['error'] = '沒有找到文章（可能期刊最近沒有更新）'
            logger.warning(f"  ⚠️ 沒有找到文章")
        
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = f'錯誤: {str(e)}'
        logger.error(f"  ❌ 錯誤: {e}")
    
    return result


def main():
    """主程式。"""
    logger.info("=" * 70)
    logger.info("開始驗證期刊（使用實際爬蟲測試）")
    logger.info("=" * 70)
    
    # 載入期刊設定
    with open('config/journals.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    journals = config['journals']
    logger.info(f"\n總共 {len(journals)} 個期刊需要驗證\n")
    
    results = []
    
    # 逐一驗證
    for idx, journal in enumerate(journals, 1):
        logger.info(f"\n[{idx}/{len(journals)}]")
        result = verify_journal_with_scraper(journal)
        results.append(result)
        logger.info("")  # 空行
    
    # 統計結果
    logger.info("=" * 70)
    logger.info("驗證結果統計")
    logger.info("=" * 70)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] == 'failed')
    no_rss_count = sum(1 for r in results if r['status'] == 'no_rss')
    
    logger.info(f"\n✅ 成功: {success_count} 個")
    logger.info(f"❌ 失敗: {failed_count} 個")
    logger.info(f"⚪ 無 RSS: {no_rss_count} 個")
    
    # 顯示詳細結果
    logger.info("\n" + "=" * 70)
    logger.info("詳細報告")
    logger.info("=" * 70)
    
    for result in results:
        status_icon = {
            'success': '✅',
            'failed': '❌',
            'no_rss': '⚪'
        }.get(result['status'], '❓')
        
        logger.info(f"\n{status_icon} {result['name']}")
        logger.info(f"   爬蟲: {result.get('scraper_class', 'N/A')}")
        logger.info(f"   RSS: {result['rss_url']}")
        
        if result['status'] == 'success':
            logger.info(f"   文章數: {result['entries_count']}")
        elif result['error']:
            logger.info(f"   錯誤: {result['error']}")
    
    # 輸出建議
    logger.info("\n" + "=" * 70)
    logger.info("建議")
    logger.info("=" * 70)
    
    if failed_count > 0:
        logger.info("\n❌ 以下期刊無法抓取資料：")
        for result in results:
            if result['status'] == 'failed':
                logger.info(f"   - {result['name']}")
                logger.info(f"     爬蟲: {result.get('scraper_class', 'N/A')}")
                logger.info(f"     錯誤: {result.get('error', 'N/A')}")
                logger.info(f"     建議: 檢查 RSS URL 或期刊網站結構是否變更")
    
    if no_rss_count > 0:
        logger.info("\n⚪ 以下期刊沒有提供 RSS URL：")
        for result in results:
            if result['status'] == 'no_rss':
                logger.info(f"   - {result['name']}")
                logger.info(f"     建議使用網頁爬蟲（ElsevierScraper）")
    
    logger.info("\n" + "=" * 70)
    logger.info("驗證完成！")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
