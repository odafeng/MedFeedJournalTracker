@echo off
REM Journal Tracker - Windows 工作排程器設定腳本

echo ====================================
echo Journal Tracker - 設定 Windows 工作排程器
echo ====================================
echo.

set PROJECT_DIR=%~dp0
set PYTHON_EXE=python

echo 專案目錄: %PROJECT_DIR%
echo Python 執行檔: %PYTHON_EXE%
echo.

echo 請執行以下命令來建立每日執行的工作排程:
echo.
echo schtasks /create /tn "JournalTracker" /tr "%PYTHON_EXE% %PROJECT_DIR%main.py" /sc daily /st 08:00 /f
echo.

echo 或者，您可以手動設定:
echo 1. 開啟「工作排程器」(Task Scheduler)
echo 2. 建立基本工作
echo 3. 名稱: Journal Tracker
echo 4. 觸發程序: 每天
echo 5. 時間: 早上 8:00
echo 6. 動作: 啟動程式
echo 7. 程式: %PYTHON_EXE%
echo 8. 引數: %PROJECT_DIR%main.py
echo 9. 起始於: %PROJECT_DIR%
echo.

pause
