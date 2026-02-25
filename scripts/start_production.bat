@echo off
REM Growth Flywheel 2.5 - One-Click Production Start
REM This script starts the complete system

echo ==========================================
echo Growth Flywheel 2.5 - Production Start
echo ==========================================
echo.

cd backend

echo [1/5] Verifying system...
python scripts\verify_system.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Some components need attention
    echo Continuing with available components...
    echo.
)

echo.
echo [2/5] Running complete demo...
python scripts\demo_complete.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Demo failed
    exit /b 1
)

echo.
echo [3/5] System is ready!
echo.
echo ==========================================
echo Next Steps:
echo ==========================================
echo.
echo Option 1: Start API Server
echo    uvicorn app.main:app --reload
echo.
echo Option 2: Start Celery Worker
echo    celery -A app.tasks.training_tasks worker --loglevel=info
echo.
echo Option 3: Start Celery Beat (Scheduler)
echo    celery -A app.tasks.training_tasks beat --loglevel=info
echo.
echo Option 4: Collect Real Data
echo    python scripts\collect_real_data.py
echo.
echo Option 5: Run Training
echo    python scripts\train_grpo_mvp.py
echo.
echo ==========================================
echo Documentation:
echo    - PRODUCTION_DEPLOYMENT_GUIDE.md
echo    - PRODUCTION_DEPLOYMENT_EXECUTION_REPORT.md
echo ==========================================
echo.

pause
