#!/bin/bash

# Growth Flywheel 2.5 - Quick Start Script
# This script sets up and runs the MVP training pipeline

set -e  # Exit on error

echo "=========================================="
echo "🚀 Growth Flywheel 2.5 - Quick Start"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+ first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"
echo ""

# Step 2: Set up environment
echo "📋 Step 2: Setting up environment..."

cd backend

if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✅ .env file created${NC}"
else
    echo -e "${YELLOW}⚠️  .env file already exists, skipping${NC}"
fi

echo ""

# Step 3: Start infrastructure services
echo "📋 Step 3: Starting infrastructure services..."

cd ..
docker-compose up -d postgres redis minio qdrant

echo "Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker ps | grep -q gf25-postgres; then
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
else
    echo -e "${RED}❌ PostgreSQL failed to start${NC}"
    exit 1
fi

if docker ps | grep -q gf25-redis; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${RED}❌ Redis failed to start${NC}"
    exit 1
fi

echo ""

# Step 4: Install Python dependencies
echo "📋 Step 4: Installing Python dependencies..."

cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate || . venv/Scripts/activate

echo "Installing requirements..."
pip install -r requirements.txt > /dev/null 2>&1

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 5: Run database migrations
echo "📋 Step 5: Running database migrations..."

alembic upgrade head

echo -e "${GREEN}✅ Database migrations complete${NC}"
echo ""

# Step 6: Create necessary directories
echo "📋 Step 6: Creating directories..."

mkdir -p checkpoints
mkdir -p logs
mkdir -p data/covers

echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Step 7: Display next steps
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1️⃣  Collect training data:"
echo "   cd backend"
echo "   python scripts/collect_data.py"
echo ""
echo "2️⃣  Run GRPO training:"
echo "   python scripts/train_grpo.py"
echo ""
echo "3️⃣  Verify results:"
echo "   python scripts/verify_training.py"
echo ""
echo "4️⃣  View dashboard:"
echo "   python scripts/dashboard.py"
echo ""
echo "5️⃣  Start API server:"
echo "   uvicorn app.main:app --reload"
echo ""
echo "=========================================="
echo "📚 Documentation:"
echo "   - Execution Guide: EXECUTION_GUIDE.md"
echo "   - Training Pipeline: TRAINING_PIPELINE_DESIGN.md"
echo "=========================================="
