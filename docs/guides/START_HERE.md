# 🚀 v4.0 部署步骤（Windows）

## ⚠️ 当前状态

Docker Desktop 未运行，需要先启动。

---

## 📋 部署步骤

### Step 1: 启动 Docker Desktop

1. 打开 Docker Desktop 应用
2. 等待 Docker 引擎启动完成（右下角图标变绿）
3. 验证 Docker 运行状态：

```powershell
docker ps
```

应该看到类似输出：
```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
```

---

### Step 2: 验证配置

已为你准备好的配置：

✅ `.env` - 环境变量已配置（使用 v4.0 Lite 模式）
✅ `docker-compose.v4.yml` - Docker Compose 配置
✅ `backend/Dockerfile` - 应用容器配置
✅ `backend/requirements.txt` - Python 依赖
✅ 所有必要目录已创建

**配置说明**：
- 使用 Claude Haiku API（需要配置 ANTHROPIC_API_KEY）
- 使用 DALL·E API（需要配置 OPENAI_API_KEY）
- 不需要 GPU
- 只支持小红书平台
- 关键决策需要人工审批

---

### Step 3: 配置 API Keys

编辑 `.env` 文件，填入你的 API Keys：

```bash
# 必填：Claude API Key
ANTHROPIC_API_KEY=sk-ant-xxxxx

# 必填：OpenAI API Key（用于 DALL·E）
OPENAI_API_KEY=sk-xxxxx
```

**获取 API Keys**：
- Claude API: https://console.anthropic.com/
- OpenAI API: https://platform.openai.com/api-keys

---

### Step 4: 启动服务

在 PowerShell 中运行：

```powershell
cd D:\growth-flywheel-2.5

# 拉取镜像
docker-compose -f docker-compose.v4.yml pull postgres redis qdrant minio prometheus grafana

# 构建应用镜像
docker-compose -f docker-compose.v4.yml build api celery-worker celery-beat

# 启动服务（v4.0 Lite - 不包括 vLLM 和 ComfyUI）
docker-compose -f docker-compose.v4.yml up -d postgres redis qdrant minio api celery-worker celery-beat prometheus grafana
```

---

### Step 5: 等待服务启动

```powershell
# 查看服务状态
docker-compose -f docker-compose.v4.yml ps

# 查看日志
docker-compose -f docker-compose.v4.yml logs -f
```

等待所有服务状态变为 `healthy` 或 `running`。

---

### Step 6: 运行数据库迁移

```powershell
# 等待 PostgreSQL 启动（约 10 秒）
Start-Sleep -Seconds 10

# 运行数据库迁移
docker-compose -f docker-compose.v4.yml exec api alembic upgrade head
```

---

### Step 7: 初始化存储

```powershell
# 初始化 MinIO buckets
docker-compose -f docker-compose.v4.yml exec minio mc alias set local http://localhost:9000 minioadmin MinIO2025!Secure
docker-compose -f docker-compose.v4.yml exec minio mc mb local/covers
docker-compose -f docker-compose.v4.yml exec minio mc mb local/videos
docker-compose -f docker-compose.v4.yml exec minio mc mb local/exports

# 初始化 Qdrant collections
Invoke-RestMethod -Uri "http://localhost:6333/collections/topics" -Method Put -Body '{"vectors":{"size":768,"distance":"Cosine"}}' -ContentType "application/json"
Invoke-RestMethod -Uri "http://localhost:6333/collections/content" -Method Put -Body '{"vectors":{"size":768,"distance":"Cosine"}}' -ContentType "application/json"
```

---

### Step 8: 验证部署

访问以下地址：

- ✅ **API 文档**: http://localhost:8080/docs
- ✅ **健康检查**: http://localhost:8080/health
- ✅ **Grafana**: http://localhost:3000 (admin / Grafana2025!Admin)
- ✅ **Prometheus**: http://localhost:9090
- ✅ **MinIO Console**: http://localhost:9001 (minioadmin / MinIO2025!Secure)
- ✅ **Qdrant Dashboard**: http://localhost:6333/dashboard

---

### Step 9: 测试 API

```powershell
# 健康检查
Invoke-RestMethod -Uri "http://localhost:8080/health"

# 发现热点话题（需要先配置 API Keys）
$body = @{
    source = "xhs_trending"
    limit = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/api/v4/account/discover-topics" -Method Post -Body $body -ContentType "application/json"
```

---

## 🎯 快速命令参考

### 查看日志
```powershell
# 所有服务
docker-compose -f docker-compose.v4.yml logs -f

# 特定服务
docker-compose -f docker-compose.v4.yml logs -f api
docker-compose -f docker-compose.v4.yml logs -f celery-worker
```

### 重启服务
```powershell
docker-compose -f docker-compose.v4.yml restart api
```

### 停止服务
```powershell
docker-compose -f docker-compose.v4.yml stop
```

### 停止并删除容器
```powershell
docker-compose -f docker-compose.v4.yml down
```

### 完全清理（包括数据）
```powershell
docker-compose -f docker-compose.v4.yml down -v
```

---

## 🔧 常见问题

### 1. 端口被占用

如果遇到端口冲突，编辑 `docker-compose.v4.yml`，修改端口映射：

```yaml
services:
  api:
    ports:
      - "8081:8080"  # 改为 8081
```

### 2. API Key 未配置

如果看到 API 调用失败，检查 `.env` 文件中的 API Keys 是否正确配置。

### 3. 数据库连接失败

```powershell
# 检查 PostgreSQL 状态
docker-compose -f docker-compose.v4.yml ps postgres

# 查看日志
docker-compose -f docker-compose.v4.yml logs postgres

# 重启数据库
docker-compose -f docker-compose.v4.yml restart postgres
```

### 4. 内存不足

如果遇到内存问题，在 Docker Desktop 设置中增加内存限制：
- Settings → Resources → Memory → 增加到 8GB+

---

## 📊 部署架构（v4.0 Lite）

```
┌─────────────────────────────────────────┐
│         Growth Brain v4.0 Lite          │
├─────────────────────────────────────────┤
│                                          │
│  应用层                                  │
│  ├─ FastAPI (8080)    - REST API       │
│  ├─ Celery Worker     - 异步任务       │
│  └─ Celery Beat       - 定时任务       │
│                                          │
│  数据层                                  │
│  ├─ PostgreSQL (5432) - 主数据库       │
│  ├─ Redis (6379)      - 缓存 + 队列    │
│  ├─ Qdrant (6333)     - 向量数据库     │
│  └─ MinIO (9000)      - 对象存储       │
│                                          │
│  监控层                                  │
│  ├─ Prometheus (9090) - 指标收集       │
│  └─ Grafana (3000)    - 可视化         │
│                                          │
│  外部 API                                │
│  ├─ Claude Haiku      - LLM 生成       │
│  └─ DALL·E 3          - 图像生成       │
│                                          │
└─────────────────────────────────────────┘
```

---

## ✅ 部署完成后

1. 访问 API 文档: http://localhost:8080/docs
2. 查看 Grafana 仪表板: http://localhost:3000
3. 开始使用 v4.0 Growth Brain！

参考文档：
- [V4.0_INTEGRATION_GUIDE.md](V4.0_INTEGRATION_GUIDE.md) - 使用指南
- [V4.0_LITE_IMPLEMENTATION.md](V4.0_LITE_IMPLEMENTATION.md) - Lite 版本说明
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - 完整部署指南

---

**准备好后，按照上述步骤操作即可！** 🚀
