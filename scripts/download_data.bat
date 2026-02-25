@echo off
REM TikTok-10M Data Download Script
REM Data will be saved to D:\SalesBoost\data

echo ============================================================
echo TikTok-10M Dataset Downloader
echo ============================================================
echo.
echo Data will be saved to: D:\SalesBoost\data
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.11+
    pause
    exit /b 1
)

REM Create data directories
echo Creating data directories...
if not exist "D:\SalesBoost\data\raw" mkdir "D:\SalesBoost\data\raw"
if not exist "D:\SalesBoost\data\processed" mkdir "D:\SalesBoost\data\processed"
echo Done!
echo.

REM Install required packages
echo Installing required packages...
pip install requests tqdm
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)
echo Done!
echo.

REM Download data
echo ============================================================
echo Step 1: Downloading TikTok-10M data (10,000 samples)
echo ============================================================
echo.
echo This will take approximately 5-10 minutes...
echo.
python backend\scripts\download_tiktok_api.py
if %errorlevel% neq 0 (
    echo ERROR: Download failed
    pause
    exit /b 1
)
echo.

REM Preprocess data
echo ============================================================
echo Step 2: Preprocessing data
echo ============================================================
echo.
python backend\scripts\preprocess_tiktok.py
if %errorlevel% neq 0 (
    echo ERROR: Preprocessing failed
    pause
    exit /b 1
)
echo.

echo ============================================================
echo Download and preprocessing completed!
echo ============================================================
echo.
echo Data saved to:
echo   Raw data: D:\SalesBoost\data\raw\tiktok-10m-sample.jsonl
echo   Processed: D:\SalesBoost\data\processed\tiktok-10m-processed.jsonl
echo.
echo Next steps:
echo   1. Check the data files
echo   2. Start the backend: cd backend ^&^& uvicorn app.main:app --reload
echo   3. Start the frontend: cd frontend ^&^& npm run dev
echo.
pause
