@echo off
REM Growth Flywheel 2.5 - 快速安装脚本 (Windows)

echo ============================================================
echo Growth Flywheel 2.5 - Environment Setup
echo ============================================================
echo.

REM 检查 Python 版本
echo [1/5] Checking Python version...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.11+
    pause
    exit /b 1
)
echo.

REM 检查磁盘空间
echo [2/5] Checking disk space...
echo WARNING: This project requires 100GB+ free space
echo   - TikTok-10M: ~50GB
echo   - JD Reviews: ~5GB
echo   - Mercari: ~10GB
echo   - Models: ~30GB
echo.
pause

REM 创建目录
echo [3/5] Creating directories...
if not exist "data\raw" mkdir data\raw
if not exist "data\processed" mkdir data\processed
if not exist "models\qwen2.5-7b-sft" mkdir models\qwen2.5-7b-sft
if not exist "models\qwen2.5-7b-grpo" mkdir models\qwen2.5-7b-grpo
if not exist "results\baseline" mkdir results\baseline
if not exist "results\experiment" mkdir results\experiment
if not exist "results\ab_test" mkdir results\ab_test
echo Done!
echo.

REM 安装依赖
echo [4/5] Installing dependencies...
echo This may take 10-15 minutes...
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
cd ..
echo Done!
echo.

REM 检查 CUDA
echo [5/5] Checking CUDA...
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
echo.

echo ============================================================
echo Installation completed!
echo ============================================================
echo.
echo Next steps:
echo   1. Download datasets:
echo      python backend\scripts\download_datasets.py
echo.
echo   2. Train SFT model:
echo      python backend\scripts\train_sft.py
echo.
echo   3. Train GRPO model:
echo      python backend\scripts\train_grpo.py
echo.
echo   4. Start backend:
echo      cd backend ^&^& uvicorn app.main:app --reload
echo.
echo   5. Start frontend:
echo      cd frontend ^&^& npm run dev
echo.
echo For detailed instructions, see QUICKSTART.md
echo.
pause
