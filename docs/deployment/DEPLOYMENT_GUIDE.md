# 🚀 v4.0 快速部署指南

## 📋 前置要求

### 必需
- Docker 20.10+
- Docker Compose 2.0+
- 16GB+ RAM
- 100GB+ 磁盘空间

### 可选（用于本地 LLM 和图像生成）
- NVIDIA GPU (24GB+ VRAM)
- NVIDIA Docker Runtime
- CUDA 12.0+

---

## 🎯 部署模式选择

### 模式 1: v4.0 Lite（推荐）
**特点**: 使用云端 API，无需 GPU，快速启动

**适用场景**:
- 初次部署
- 无 GPU 环境
- 快速验证

**成本**: ~$100/月（API 调用）

### 模式 2: v4.0 Full（高级）
**特点**: 本地部署 LLM 和图像生成，需要 GPU

**适用场景**:
- 有 GPU 资源
- 追求极致性能
- 降低长期成本

**成本**: ~$85/月（电费 + 存储）+ $4000（GPU 前期投入）

---

## 🚀 快速部署（v4.0 Lite）

### Step 1: 克隆项目

```bash
git clone <repository-url>
cd growth-flywheel-2.5
```

### Step 2: 配置环境变量

```bash
# Linux/Mac
cp .env.example .env

# Windows
copy .env.example .env
```

编辑 `.env` 文件，填入必要配置：

```bash
# 必填项
POSTGRES_PASSWORD=your_secure_password
ANTHROPIC_API_KEY=sk-ant-xxx  # Claude API
OPENAI_API_KEY=sk-xxx          # DALL·E API

# v4.0 Lite 配置
ENABLE_AUTO_ACCOUNT_MANAGER=true
ENABLE_MULTIMODAL_COVER=true
ENABLE_MULTI_PLATFORM=false     # 只支持小红书
ENABLE_CAUSAL_INFERENCE=false   # 样本不足时禁用
ENABLE_AUTO_PUBLISH=false       # 需要人工审批

# LLM 配置（Lite 模式使用云端 API）
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-20241022
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=gpt-4o-mini

# 图像生成配置（Lite 模式使用 DALL·E）
IMAGE_PROVIDER=dalle
IMAGE_FALLBACK_PROVIDER=dalle
```

### Step 3: 运行部署脚本

**Linux/Mac**:
```bash
chmod +x deploy.sh
./deploy.sh
```

**Windows**:
```powershell
.\deploy.ps1
```

### Step 4: 验证部署

访问以下地址验证服务：

- API 文档: http://localhost:8080/docs
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- MinIO Console: http://localhost:9001

### Step 5: 运行数据库迁移

```bash
docker-compose -f docker-compose.v4.yml exec api alembic upgrade head
```

### Step 6: 测试 API

```bash
# 健康检查
curl http://localhost:8080/health

# 发现热点话题
curl -X POST http://localhost:8080/api/v4/account/discover-topics \
  -H "Content-Type: application/json" \
  -d '{
    "source": "xhs_trending",
    "limit": 5
  }'
```

---

## 🎮 高级部署（v4.0 Full with GPU）

### 额外前置要求

1. 安装 NVIDIA Docker Runtime:

```bash
# Ubuntu
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

2. 验证 GPU 可用:

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 配置 v4.0 Full

编辑 `.env`:

```bash
# LLM 配置（使用本地 vLLM）
LLM_PROVIDER=vllm
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
VLLM_API_KEY=your_vllm_key

# 图像生成配置（使用本地 ComfyUI）
IMAGE_PROVIDER=comfyui
COMFYUI_API_BASE=http://comfyui:8188
```

### 部署

```bash
# 运行完整部署（包括 GPU 服务）
./deploy.sh
```

部署脚本会自动检测 GPU 并启动 vLLM 和 ComfyUI。

### 验证 GPU 服务

```bash
# 检查 vLLM
curl http://localhost:8000/v1/models

# 检查 ComfyUI
curl http://localhost:8188/system_stats
```

---

## 📊 监控与日志

### 查看日志

```bash
# 所有服务
docker-compose -f docker-compose.v4.yml logs -f

# 特定服务
docker-compose -f docker-compose.v4.yml logs -f api
docker-compose -f docker-compose.v4.yml logs -f celery-worker
```

### Grafana 仪表板

1. 访问 http://localhost:3000
2. 登录（admin / 见 .env 中的 GRAFANA_PASSWORD）
3. 导入预配置的仪表板

### Prometheus 指标

访问 http://localhost:9090 查看原始指标。

---

## 🔧 常见问题

### 1. 数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose -f docker-compose.v4.yml ps postgres

# 查看日志
docker-compose -f docker-compose.v4.yml logs postgres

# 重启数据库
docker-compose -f docker-compose.v4.yml restart postgres
```

### 2. Redis 连接失败

```bash
# 检查 Redis 状态
docker-compose -f docker-compose.v4.yml exec redis redis-cli ping

# 应该返回 PONG
```

### 3. GPU 服务启动失败

```bash
# 检查 GPU 可用性
nvidia-smi

# 检查 NVIDIA Docker Runtime
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# 查看 vLLM 日志
docker-compose -f docker-compose.v4.yml logs vllm
```

### 4. API 响应慢

检查以下配置：

```bash
# .env
CACHE_L1_MAX_SIZE=1000
CACHE_L2_TTL_SECONDS=3600
PARALLEL_EXECUTOR_MAX_WORKERS=10
```

增加缓存大小和并行度。

### 5. 内存不足

如果遇到 OOM 错误：

```bash
# 限制服务内存
# 编辑 docker-compose.v4.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 4G
```

---

## 🛑 停止和清理

### 停止服务

```bash
docker-compose -f docker-compose.v4.yml stop
```

### 停止并删除容器

```bash
docker-compose -f docker-compose.v4.yml down
```

### 完全清理（包括数据）

```bash
docker-compose -f docker-compose.v4.yml down -v
```

⚠️ 警告：这会删除所有数据！

---

## 📈 性能优化

### 1. 启用多层缓存

确保 Redis 正常运行：

```bash
docker-compose -f docker-compose.v4.yml exec redis redis-cli INFO stats
```

### 2. 调整并行度

编辑 `.env`:

```bash
PARALLEL_EXECUTOR_MAX_WORKERS=20  # 根据 CPU 核心数调整
```

### 3. 使用 SSD

确保 Docker 数据目录在 SSD 上：

```bash
docker info | grep "Docker Root Dir"
```

### 4. 启用 HTTP/2

在 Nginx 或负载均衡器中启用 HTTP/2。

---

## 🔐 安全建议

### 1. 修改默认密码

编辑 `.env`，修改所有密码：

```bash
POSTGRES_PASSWORD=<strong-password>
MINIO_ROOT_PASSWORD=<strong-password>
GRAFANA_PASSWORD=<strong-password>
```

### 2. 限制网络访问

编辑 `docker-compose.v4.yml`，移除不必要的端口暴露：

```yaml
services:
  postgres:
    # ports:
    #   - "5432:5432"  # 注释掉，只允许内部访问
```

### 3. 启用 HTTPS

使用 Nginx 或 Traefik 作为反向代理，配置 SSL 证书。

### 4. 定期备份

```bash
# 备份数据库
docker-compose -f docker-compose.v4.yml exec postgres pg_dump -U growth_user growth_flywheel > backup.sql

# 备份 MinIO
docker-compose -f docker-compose.v4.yml exec minio mc mirror local/covers ./backup/covers
```

---

## 📚 下一步

部署完成后，参考以下文档：

- [V4.0_INTEGRATION_GUIDE.md](V4.0_INTEGRATION_GUIDE.md) - 集成指南
- [V4.0_LITE_IMPLEMENTATION.md](V4.0_LITE_IMPLEMENTATION.md) - Lite 版本说明
- [V4.0_HIGH_PERFORMANCE_ROUTING.md](V4.0_HIGH_PERFORMANCE_ROUTING.md) - 性能优化
- [V4.0_EXTREME_OPTIMIZATION.md](V4.0_EXTREME_OPTIMIZATION.md) - 极致优化

---

**部署完成！开始使用 Growth Brain v4.0 🎉**
