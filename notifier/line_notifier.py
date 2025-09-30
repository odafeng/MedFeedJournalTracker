"""Line Messaging API notifier for sending journal updates."""

import requests
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger("journal_tracker")


class LineNotifier:
    """Line Messaging API 通知器，負責推播期刊更新訊息。"""
    
    # Line 單則訊息最多 5000 字元
    MAX_MESSAGE_LENGTH = 5000
    
    def __init__(self, channel_access_token: str):
        """
        初始化 Line 通知器。
        
        Args:
            channel_access_token: Line Channel Access Token
        """
        self.channel_access_token = channel_access_token
        self.api_url = "https://api.line.me/v2/bot/message/push"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.channel_access_token}'
        }
        logger.info("Line 通知器初始化成功")
    
    def format_message(
        self, 
        subscriber_name: str, 
        category: str, 
        articles_by_journal: Dict[str, List[Dict]]
    ) -> str:
        """
        格式化訊息（針對單一訂閱者和單一類別）。
        
        Args:
            subscriber_name: 訂閱者名稱
            category: 類別（CRC 或 SDS）
            articles_by_journal: 按期刊分組的文章字典
                格式: {journal_name: [article1, article2, ...]}
        
        Returns:
            str: 格式化的訊息
        
        訊息格式範例:
            📚 陳教授 的期刊更新 (2025/09/30)
            類別：SDS
            
            【IEEE Transactions on Medical Imaging】
            1. Deep Learning for MRI Reconstruction
               DOI: 10.1109/TMI.2025.12345
               🔗 https://ieeexplore.ieee.org/...
            
            【Nature Machine Intelligence】
            1. Federated Learning in Healthcare
               DOI: 10.1038/s42256-025-00123
               🔗 https://nature.com/...
            
            ---
            共發現 15 篇新文章
        """
        # 計算總文章數
        total_articles = sum(len(articles) for articles in articles_by_journal.values())
        
        # 訊息標題
        today = datetime.now().strftime('%Y/%m/%d')
        message = f"📚 {subscriber_name} 的期刊更新 ({today})\n"
        message += f"類別：{category}\n"
        message += f"📅 顯示過去 7 天內的新文章\n"
        message += f"\n"
        
        # 按期刊分組顯示文章
        for journal_name, articles in articles_by_journal.items():
            message += f"【{journal_name}】\n"
            
            for idx, article in enumerate(articles, 1):
                # 文章標題（限制長度）
                title = article['title']
                if len(title) > 100:
                    title = title[:97] + "..."
                
                message += f"{idx}. {title}\n"
                message += f"   DOI: {article['doi']}\n"
                
                # 作者（如果有）
                if article.get('authors'):
                    authors = article['authors']
                    if len(authors) > 80:
                        authors = authors[:77] + "..."
                    message += f"   作者: {authors}\n"
                
                # URL
                message += f"   🔗 {article['url']}\n"
                
                # 發表日期（如果有）
                if article.get('published_date'):
                    message += f"   📅 {article['published_date']}\n"
                
                message += "\n"
            
            message += "\n"
        
        # 訊息結尾
        message += "---\n"
        message += f"📊 共發現 {total_articles} 篇新文章（過去 7 天）\n"
        
        return message
    
    def send_notification(self, user_id: str, message: str) -> bool:
        """
        推播訊息到指定 Line 使用者。
        
        Args:
            user_id: Line 使用者 ID
            message: 訊息內容
        
        Returns:
            bool: 推播成功返回 True，失敗返回 False
        """
        try:
            # 檢查訊息長度
            if len(message) > self.MAX_MESSAGE_LENGTH:
                logger.warning(f"訊息過長 ({len(message)} 字元)，將分批發送")
                return self._send_long_message(user_id, message)
            
            # 準備請求資料
            data = {
                'to': user_id,
                'messages': [
                    {
                        'type': 'text',
                        'text': message
                    }
                ]
            }
            
            # 發送請求
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=data,
                timeout=10
            )
            
            # 檢查回應
            if response.status_code == 200:
                logger.info(f"成功推播訊息給使用者: {user_id}")
                return True
            else:
                logger.error(
                    f"推播失敗 (Status {response.status_code}): "
                    f"{response.text}"
                )
                return False
                
        except requests.RequestException as e:
            logger.error(f"推播請求失敗: {e}")
            return False
        except Exception as e:
            logger.error(f"推播時發生錯誤: {e}")
            return False
    
    def _send_long_message(self, user_id: str, message: str) -> bool:
        """
        處理過長的訊息，分批發送。
        
        Args:
            user_id: Line 使用者 ID
            message: 長訊息內容
        
        Returns:
            bool: 所有訊息都成功發送返回 True
        """
        # 將訊息分割成多個部分
        parts = self._split_message(message)
        
        logger.info(f"訊息將分成 {len(parts)} 部分發送")
        
        success_count = 0
        for idx, part in enumerate(parts, 1):
            # 在每個部分前面加上標記
            if len(parts) > 1:
                part_message = f"[{idx}/{len(parts)}]\n\n{part}"
            else:
                part_message = part
            
            # 發送
            if self.send_notification(user_id, part_message):
                success_count += 1
            else:
                logger.error(f"發送第 {idx} 部分失敗")
        
        return success_count == len(parts)
    
    def _split_message(self, message: str) -> List[str]:
        """
        將長訊息分割成多個部分。
        
        Args:
            message: 原始訊息
        
        Returns:
            List[str]: 分割後的訊息列表
        """
        # 預留空間給部分標記 "[1/3]\n\n"
        max_part_length = self.MAX_MESSAGE_LENGTH - 20
        
        # 嘗試按段落分割
        paragraphs = message.split('\n\n')
        
        parts = []
        current_part = ""
        
        for paragraph in paragraphs:
            # 如果單個段落就超過長度限制
            if len(paragraph) > max_part_length:
                # 先儲存當前部分
                if current_part:
                    parts.append(current_part.strip())
                    current_part = ""
                
                # 按行分割這個段落
                lines = paragraph.split('\n')
                for line in lines:
                    if len(current_part) + len(line) + 1 <= max_part_length:
                        current_part += line + '\n'
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = line + '\n'
            else:
                # 檢查加入這個段落是否會超過長度
                if len(current_part) + len(paragraph) + 2 <= max_part_length:
                    current_part += paragraph + '\n\n'
                else:
                    # 儲存當前部分，開始新部分
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
        
        # 加入最後一部分
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    def send_batch_notifications(
        self, 
        subscribers: List[Dict], 
        articles_by_category: Dict[str, Dict[str, List[Dict]]]
    ) -> Dict[str, bool]:
        """
        批量發送通知給多個訂閱者。
        
        Args:
            subscribers: 訂閱者列表
            articles_by_category: 按類別和期刊分組的文章
                格式: {
                    'CRC': {journal_name: [articles]},
                    'SDS': {journal_name: [articles]}
                }
        
        Returns:
            Dict[str, bool]: 訂閱者 ID 對應的發送結果
        """
        results = {}
        
        for subscriber in subscribers:
            subscriber_id = subscriber['id']
            subscriber_name = subscriber['name']
            line_user_id = subscriber['line_user_id']
            category = subscriber['subscribed_category']
            
            # 取得該類別的文章
            articles_by_journal = articles_by_category.get(category, {})
            
            if not articles_by_journal:
                logger.info(
                    f"訂閱者 {subscriber_name} 沒有 {category} 類別的新文章"
                )
                results[subscriber_id] = True  # 沒有文章也算成功
                continue
            
            # 格式化訊息
            message = self.format_message(
                subscriber_name, 
                category, 
                articles_by_journal
            )
            
            # 發送通知
            success = self.send_notification(line_user_id, message)
            results[subscriber_id] = success
            
            if success:
                total_articles = sum(
                    len(articles) for articles in articles_by_journal.values()
                )
                logger.info(
                    f"成功推播 {total_articles} 篇文章給 {subscriber_name}"
                )
            else:
                logger.error(f"推播失敗: {subscriber_name}")
        
        return results
