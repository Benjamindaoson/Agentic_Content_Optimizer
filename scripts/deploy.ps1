# v4.0 Growth Brain 部署脚本 (Windows)

Write-Host "🚀 开始部署 Growth Flywheel v4.0..." -ForegroundColor Green

# 检查 Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker 未安装，请先安装 Docker Desktop" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose 未安装，请先安装 Docker Compose" -ForegroundColor Red
    exit 1
}

# 检查 NVIDIA GPU（可选）
$GPU_AVAILABLE = $false
try {
    nvidia-smi | Out-Null
    Write-Host "✅ 检测到 NVIDIA GPU" -ForegroundColor Green
    $GPU_AVAILABLE = $true
} catch {
    Write-Host "⚠️  未检测到 NVIDIA GPU，将跳过 vLLM 和 ComfyUI 部署" -ForegroundColor Yellow
}

# 检查 .env 文件
if (-not (Test-Path .env)) {
    Write-Host "📝 创建 .env 文件..." -ForegroundColor Cyan
    Copy-Item .env.example .env
    Write-Host "⚠️  请编辑 .env 文件，填入必要的配置" -ForegroundColor Yellow
    Write-Host "   特别是以下配置：" -ForegroundColor Yellow
    Write-Host "   - POSTGRES_PASSWORD" -ForegroundColor Yellow
    Write-Host "   - ANTHROPIC_API_KEY" -ForegroundColor Yellow
    Write-Host "   - OPENAI_API_KEY" -ForegroundColor Yellow
    Read-Host "按 Enter 继续"
}

# 创建必要的目录
Write-Host "📁 创建必要的目录..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path logs | Out-Null
New-Item -ItemType Directory -Force -Path monitoring\grafana\dashboards | Out-Null
New-Item -ItemType Directory -Force -Path monitoring\grafana\datasources | Out-Null
New-Item -ItemType Directory -Force -Path comfyui\workflows | Out-Null
New-Item -ItemType Directory -Force -Path scripts | Out-Null

# 初始化数据库脚本
$initDbSql = @"
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置时区
SET timezone = 'Asia/Shanghai';
"@
$initDbSql | Out-File -FilePath scripts\init_db.sql -Encoding UTF8

# 拉取镜像
Write-Host "📦 拉取 Docker 镜像..." -ForegroundColor Cyan
docker-compose -f docker-compose.v4.yml pull

# 构建自定义镜像
Write-Host "🔨 构建应用镜像..." -ForegroundColor Cyan
docker-compose -f docker-compose.v4.yml build

# 启动基础服务
Write-Host "🚀 启动基础服务..." -ForegroundColor Cyan
if ($GPU_AVAILABLE) {
    docker-compose -f docker-compose.v4.yml up -d
} else {
    # 不启动 vLLM 和 ComfyUI
    docker-compose -f docker-compose.v4.yml up -d postgres redis qdrant minio api celery-worker celery-beat prometheus grafana
}

# 等待数据库启动
Write-Host "⏳ 等待数据库启动..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# 运行数据库迁移
Write-Host "🗄️  运行数据库迁移..." -ForegroundColor Cyan
docker-compose -f docker-compose.v4.yml exec -T api alembic upgrade head

# 初始化 MinIO buckets
Write-Host "🪣 初始化 MinIO buckets..." -ForegroundColor Cyan
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/covers 2>$null
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/videos 2>$null
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/exports 2>$null

# 初始化 Qdrant collections
Write-Host "🔍 初始化 Qdrant collections..." -ForegroundColor Cyan
$topicsCollection = @{
    vectors = @{
        size = 768
        distance = "Cosine"
    }
} | ConvertTo-Json

$contentCollection = @{
    vectors = @{
        size = 768
        distance = "Cosine"
    }
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "http://localhost:6333/collections/topics" -Method Put -Body $topicsCollection -ContentType "application/json" | Out-Null
    Invoke-RestMethod -Uri "http://localhost:6333/collections/content" -Method Put -Body $contentCollection -ContentType "application/json" | Out-Null
} catch {
    Write-Host "⚠️  Qdrant collections 可能已存在" -ForegroundColor Yellow
}

# 显示服务状态
Write-Host ""
Write-Host "✅ 部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "📊 服务访问地址：" -ForegroundColor Cyan
Write-Host "   - API 文档: http://localhost:8080/docs"
Write-Host "   - Grafana: http://localhost:3000 (admin / 见 .env)"
Write-Host "   - Prometheus: http://localhost:9090"
Write-Host "   - MinIO Console: http://localhost:9001"
Write-Host "   - Qdrant Dashboard: http://localhost:6333/dashboard"

if ($GPU_AVAILABLE) {
    Write-Host "   - vLLM API: http://localhost:8000/docs"
    Write-Host "   - ComfyUI: http://localhost:8188"
}

Write-Host ""
Write-Host "📝 查看日志：" -ForegroundColor Cyan
Write-Host "   docker-compose -f docker-compose.v4.yml logs -f"
Write-Host ""
Write-Host "🛑 停止服务：" -ForegroundColor Cyan
Write-Host "   docker-compose -f docker-compose.v4.yml down"
Write-Host ""
