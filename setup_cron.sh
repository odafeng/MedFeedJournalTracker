#!/bin/bash
# Journal Tracker - Cron Job 設定腳本
# 此腳本協助您設定每日自動執行

# 取得專案目錄的絕對路徑
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python 執行檔路徑（可能需要根據您的環境調整）
PYTHON_PATH=$(which python3)

# 建立 logs 目錄
mkdir -p "$PROJECT_DIR/logs"

# Cron 設定（每天早上 6:00 執行，UTC+8）
CRON_SCHEDULE="0 6 * * *"
CRON_COMMAND="cd $PROJECT_DIR && $PYTHON_PATH $PROJECT_DIR/main.py >> $PROJECT_DIR/logs/cron.log 2>&1"

echo "=" 
echo "Journal Tracker - Cron Job 設定"
echo "="
echo ""
echo "專案目錄: $PROJECT_DIR"
echo "Python 路徑: $PYTHON_PATH"
echo "執行時間: 每天早上 6:00 (UTC+8)"
echo ""
echo "Cron 設定內容:"
echo "$CRON_SCHEDULE $CRON_COMMAND"
echo ""
echo "請執行以下命令來設定 cron job:"
echo ""
echo "  crontab -e"
echo ""
echo "然後加入以下這一行:"
echo ""
echo "$CRON_SCHEDULE $CRON_COMMAND"
echo ""
echo "或者，如果您信任此腳本，可以執行:"
echo ""
echo '  (crontab -l 2>/dev/null; echo "'"$CRON_SCHEDULE $CRON_COMMAND"'") | crontab -'
echo ""
