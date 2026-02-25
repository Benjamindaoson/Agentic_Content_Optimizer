@echo off
REM Growth Flywheel 2.5 - Quick Start Script (Windows)
REM This script sets up and runs the MVP training pipeline

setlocal enabledelayedexpansion

echo ==========================================
echo 🚀 Growth Flywheel 2.5 - Quick Start
echo ==========================================
echo.

REM Step 1: Check prerequisites
echo 📋 Step 1: Checking prerequisites...

where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker not found. Please install Docker Desktop first.
    exit /b 1
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Compose not found. Please install Docker Compose first.
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python not found. Please install Python 3.9+ first.
    exit /b 1
)

echo ✅ All prerequisites met
echo.

REM Step 2: Set up environment
echo 📋 Step 2: Setting up environment...

cd backend

if not exist .env (
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo ✅ .env file created
) else (
    echo ⚠️  .env file already exists, skipping
)

echo.

REM Step 3: Start infrastructure services
echo 📋 Step 3: Starting infrastructure services...

cd ..
docker-compose up -d postgres redis minio qdrant

echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

REM Check if services are running
docker ps | findstr gf25-postgres >nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ PostgreSQL is running
) else (
    echo ❌ PostgreSQL failed to start
    exit /b 1
)

docker ps | findstr gf25-redis >nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Redis is running
) else (
    echo ❌ Redis failed to start
    exit /b 1
)

echo.

REM Step 4: Install Python dependencies
echo 📋 Step 4: Installing Python dependencies...

cd backend

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt >nul 2>&1

echo ✅ Dependencies installed
echo.

REM Step 5: Run database migrations
echo 📋 Step 5: Running database migrations...

alembic upgrade head

echo ✅ Database migrations complete
echo.

REM Step 6: Create necessary directories
echo 📋 Step 6: Creating directories...

if not exist checkpoints mkdir checkpoints
if not exist logs mkdir logs
if not exist data\covers mkdir data\covers

echo ✅ Directories created
echo.

REM Step 7: Display next steps
echo ==========================================
echo ✅ Setup Complete!
echo ==========================================
echo.
echo Next steps:
echo.
echo 1️⃣  Collect training data:
echo    cd backend
echo    python scripts\collect_data.py
echo.
echo 2️⃣  Run GRPO training:
echo    python scripts\train_grpo.py
echo.
echo 3️⃣  Verify results:
echo    python scripts\verify_training.py
echo.
echo 4️⃣  View dashboard:
echo    python scripts\dashboard.py
echo.
echo 5️⃣  Start API server:
echo    uvicorn app.main:app --reload
echo.
echo ==========================================
echo 📚 Documentation:
echo    - Execution Guide: EXECUTION_GUIDE.md
echo    - Training Pipeline: TRAINING_PIPELINE_DESIGN.md
echo ==========================================

pause
