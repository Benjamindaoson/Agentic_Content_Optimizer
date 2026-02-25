@echo off
REM TikTok-10M FULL Dataset Download Script
REM Downloads all 10 MILLION records (~50GB)

echo ============================================================
echo TikTok-10M FULL Dataset Downloader
echo ============================================================
echo.
echo WARNING: This will download 10 MILLION records!
echo.
echo Estimated:
echo   - Size: ~50GB
echo   - Time: 50-80 hours
echo   - Location: D:\SalesBoost\data\raw\tiktok-10m-full.jsonl
echo.
echo Features:
echo   - Supports resume (if interrupted, run again to continue)
echo   - Auto-saves every 10,000 records
echo   - Handles rate limits automatically
echo.
echo ============================================================
echo.

pause

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install requests tqdm
echo.

REM Create directories
if not exist "D:\SalesBoost\data\raw" mkdir "D:\SalesBoost\data\raw"
if not exist "D:\SalesBoost\data\processed" mkdir "D:\SalesBoost\data\processed"

REM Start download
echo ============================================================
echo Starting download...
echo ============================================================
echo.
python backend\scripts\download_tiktok_full.py

echo.
echo ============================================================
echo Download script finished!
echo ============================================================
echo.
echo Check D:\SalesBoost\data\raw\tiktok-10m-full.jsonl
echo.
pause
