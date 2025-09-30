"""Logger utility for journal tracker."""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "journal_tracker", log_level: str = None) -> logging.Logger:
    """
    設定並返回 logger 實例。
    
    Args:
        name: Logger 名稱
        log_level: 日誌級別（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    
    Returns:
        logging.Logger: 設定好的 logger 實例
    """
    # 從環境變數取得 log level，預設為 INFO
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # 建立 logs 目錄
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 建立 logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 建立 formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    log_file = log_dir / f"journal_tracker_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
