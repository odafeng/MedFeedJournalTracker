"""驗證所有期刊的 RSS feed 是否可用。"""

import json
import feedparser
import requests
from utils.logger import setup_logger

logger = setup_logger("verify_rss")


def verify_rss_feed(name: str, rss_url: str) -> dict:
    """
    驗證單一 RSS feed。
    
    Returns:
        dict: {
            'name': 期刊名稱,
            'rss_url': RSS URL,
            'status': 'success' | 'failed' | 'no_rss',
            'entries_count': 文章數量,
            'error': 錯誤訊息（如果有）
        }
    """
    result = {
        'name': name,
        'rss_url': rss_url,
        'status': 'unknown',
        'entries_count': 0,
        'error': None
    }
    
    if not rss_url:
        result['status'] = 'no_rss'
        result['error'] = '未提供 RSS URL'
        return result
    
    try:
        logger.info(f"測試: {name}")
        logger.info(f"  RSS URL: {rss_url}")
        
        # 先測試 URL 是否可訪問
        response = requests.head(rss_url, timeout=10)
        logger.info(f"  HTTP Status: {response.status_code}")
        
        # 解析 RSS
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            result['status'] = 'failed'
            result['error'] = f'RSS 格式錯誤: {feed.bozo_exception}'
            logger.warning(f"  ❌ RSS 格式錯誤")
        elif not feed.entries:
            result['status'] = 'failed'
            result['error'] = 'RSS feed 中沒有文章'
            logger.warning(f"  ⚠️ 沒有文章")
        else:
            result['status'] = 'success'
            result['entries_count'] = len(feed.entries)
            logger.info(f"  ✅ 成功！找到 {len(feed.entries)} 篇文章")
            
            # 顯示第一篇文章的標題
            if feed.entries:
                first_title = feed.entries[0].get('title', 'N/A')
                logger.info(f"  第一篇: {first_title[:60]}...")
        
    except requests.RequestException as e:
        result['status'] = 'failed'
        result['error'] = f'網路請求失敗: {str(e)}'
        logger.error(f"  ❌ 網路錯誤: {e}")
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = f'未知錯誤: {str(e)}'
        logger.error(f"  ❌ 錯誤: {e}")
    
    return result


def main():
    """主程式。"""
    logger.info("=" * 70)
    logger.info("開始驗證期刊 RSS Feeds")
    logger.info("=" * 70)
    
    # 載入期刊設定
    with open('config/journals.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    journals = config['journals']
    logger.info(f"\n總共 {len(journals)} 個期刊需要驗證\n")
    
    results = []
    
    # 逐一驗證
    for journal in journals:
        result = verify_rss_feed(journal['name'], journal.get('rss_url'))
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
        logger.info("\n❌ 以下期刊的 RSS feed 無法使用，需要更新：")
        for result in results:
            if result['status'] == 'failed':
                logger.info(f"   - {result['name']}")
                logger.info(f"     請訪問期刊官網尋找正確的 RSS URL")
    
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
