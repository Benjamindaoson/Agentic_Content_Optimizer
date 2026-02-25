#!/bin/bash

# v4.0 Growth Brain 部署脚本

set -e

echo "🚀 开始部署 Growth Flywheel v4.0..."

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 检查 NVIDIA GPU（可选）
if command -v nvidia-smi &> /dev/null; then
    echo "✅ 检测到 NVIDIA GPU"
    GPU_AVAILABLE=true
else
    echo "⚠️  未检测到 NVIDIA GPU，将跳过 vLLM 和 ComfyUI 部署"
    GPU_AVAILABLE=false
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，填入必要的配置"
    echo "   特别是以下配置："
    echo "   - POSTGRES_PASSWORD"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - OPENAI_API_KEY"
    read -p "按 Enter 继续..."
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources
mkdir -p comfyui/workflows
mkdir -p scripts

# 初始化数据库脚本
cat > scripts/init_db.sql << 'EOF'
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置时区
SET timezone = 'Asia/Shanghai';

-- 创建初始用户（如果需要）
-- INSERT INTO users (username, email) VALUES ('admin', 'admin@example.com');
EOF

# 拉取镜像
echo "📦 拉取 Docker 镜像..."
docker-compose -f docker-compose.v4.yml pull

# 构建自定义镜像
echo "🔨 构建应用镜像..."
docker-compose -f docker-compose.v4.yml build

# 启动基础服务（不包括 GPU 服务）
echo "🚀 启动基础服务..."
if [ "$GPU_AVAILABLE" = true ]; then
    docker-compose -f docker-compose.v4.yml up -d
else
    # 不启动 vLLM 和 ComfyUI
    docker-compose -f docker-compose.v4.yml up -d postgres redis qdrant minio api celery-worker celery-beat prometheus grafana
fi

# 等待数据库启动
echo "⏳ 等待数据库启动..."
sleep 10

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
docker-compose -f docker-compose.v4.yml exec -T api alembic upgrade head

# 初始化 MinIO buckets
echo "🪣 初始化 MinIO buckets..."
docker-compose -f docker-compose.v4.yml exec -T minio mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD || true
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/covers || true
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/videos || true
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/exports || true

# 初始化 Qdrant collections
echo "🔍 初始化 Qdrant collections..."
curl -X PUT "http://localhost:6333/collections/topics" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }' || true

curl -X PUT "http://localhost:6333/collections/content" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }' || true

# 显示服务状态
echo ""
echo "✅ 部署完成！"
echo ""
echo "📊 服务访问地址："
echo "   - API 文档: http://localhost:8080/docs"
echo "   - Grafana: http://localhost:3000 (admin / 见 .env)"
echo "   - Prometheus: http://localhost:9090"
echo "   - MinIO Console: http://localhost:9001"
echo "   - Qdrant Dashboard: http://localhost:6333/dashboard"

if [ "$GPU_AVAILABLE" = true ]; then
    echo "   - vLLM API: http://localhost:8000/docs"
    echo "   - ComfyUI: http://localhost:8188"
fi

echo ""
echo "📝 查看日志："
echo "   docker-compose -f docker-compose.v4.yml logs -f"
echo ""
echo "🛑 停止服务："
echo "   docker-compose -f docker-compose.v4.yml down"
echo ""
