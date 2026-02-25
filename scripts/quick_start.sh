#!/bin/bash

# =============================================================================
# Growth Flywheel 2.5 — Lite Edition 快速启动脚本
# =============================================================================

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}🚀 正在准备启动 Growth Flywheel 2.5 (Lite Edition)...${NC}"

# 1. 检查环境变量
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  未发现 .env 文件，正在从模板创建...${NC}"
    cp .env.lite.example .env
    echo -e "${GREEN}✅ .env 文件已创建。请在该文件中填入您的 LLM API Key (如 DEEPSEEK_API_KEY)。${NC}"
else
    echo -e "${GREEN}✅ 发现已存在的 .env 文件。${NC}"
fi

# 2. 检查 Docker 环境
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 错误: 未安装 Docker。请先安装 Docker。${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}❌ 错误: Docker 未启动。请先启动 Docker 服务。${NC}"
    exit 1
fi

# 3. 启动容器
echo -e "${BLUE}🐳 正在通过 Docker Compose 启动服务...${NC}"
docker compose -f docker-compose.lite.yml up -d

# 4. 等待关键服务启动
echo -e "${BLUE}⏳ 等待后端服务就绪 (可能需要 1-2 分钟)...${NC}"
max_retries=30
count=0
until $(curl --output /dev/null --silent --head --fail http://localhost:8080/health); do
    printf '.'
    sleep 3
    count=$((count+1))
    if [ $count -gt $max_retries ]; then
        echo -e "\n${RED}❌ 错误: 后端服务启动超时。请执行 'docker compose -f docker-compose.lite.yml logs api' 检查日志。${NC}"
        exit 1
    fi
done

echo -e "\n${GREEN}✨ 全部服务已就绪!${NC}"
echo -e "----------------------------------------------------------------"
echo -e "📱 前端界面: ${BLUE}http://localhost:3000${NC}"
echo -e "⚙️  后端 API: ${BLUE}http://localhost:8080${NC}"
echo -e "📑 API 文档: ${BLUE}http://localhost:8080/docs${NC}"
echo -e "----------------------------------------------------------------"
echo -e "${YELLOW}提示: 如果内容生成不成功，请检查 .env 中的 API KEY 是否有效。${NC}"
