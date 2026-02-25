# Growth Flywheel 2.5 - 生产部署指南

## 快速开始

### 1. 环境要求

**必需**:
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Qdrant 1.7+

**可选**:
- Docker & Docker Compose
- Nginx (生产环境)

---

## 一、本地开发部署

### 1.1 克隆项目

```bash
git clone <repository-url>
cd growth-flywheel-2.5/backend
```

### 1.2 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 1.3 安装依赖

```bash
pip install -r requirements.txt
```

### 1.4 配置环境变量

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# 环境
ENVIRONMENT=development

# 数据库
DATABASE_URL=postgresql://user:password@localhost:5432/growth_flywheel
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-in-production-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# LLM API Keys
ANTHROPIC_API_KEY=your-claude-api-key
OPENAI_API_KEY=your-openai-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
GOOGLE_API_KEY=your-gemini-api-key
DOTS_API_KEY=your-dots-api-key

# 日志
LOG_LEVEL=INFO
```

### 1.5 初始化数据库

```bash
# 创建数据库
createdb growth_flywheel

# 运行迁移
python migrate.py upgrade
```

### 1.6 启动服务

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用脚本
python run.py
```

访问：
- API: http://localhost:8000
- 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

---

## 二、Docker 部署

### 2.1 使用 Docker Compose（推荐）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: growth_flywheel
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Qdrant
  qdrant:
    image: qdrant/qdrant:v1.7.4
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  # Backend API
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/growth_flywheel
      REDIS_URL: redis://redis:6379/0
      QDRANT_HOST: qdrant
      QDRANT_PORT: 6333
      ENVIRONMENT: production
      JWT_SECRET: ${JWT_SECRET}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
      - qdrant
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

启动：

```bash
docker-compose up -d
```

### 2.2 单独构建 Docker 镜像

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
docker build -t growth-flywheel-backend .
docker run -p 8000:8000 --env-file .env growth-flywheel-backend
```

---

## 三、生产环境部署

### 3.1 使用 Gunicorn + Uvicorn Workers

安装：

```bash
pip install gunicorn
```

启动：

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### 3.2 Nginx 反向代理

创建 `/etc/nginx/sites-available/growth-flywheel`：

```nginx
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    # 请求体大小限制
    client_max_body_size 10M;

    # 代理设置
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 静态文件（如果有）
    location /static {
        alias /var/www/growth-flywheel/static;
        expires 30d;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/growth-flywheel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3.3 SSL/TLS 配置（Let's Encrypt）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

### 3.4 Systemd 服务

创建 `/etc/systemd/system/growth-flywheel.service`：

```ini
[Unit]
Description=Growth Flywheel Backend API
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/growth-flywheel/backend
Environment="PATH=/var/www/growth-flywheel/backend/venv/bin"
EnvironmentFile=/var/www/growth-flywheel/backend/.env
ExecStart=/var/www/growth-flywheel/backend/venv/bin/gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 120
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable growth-flywheel
sudo systemctl start growth-flywheel
sudo systemctl status growth-flywheel
```

---

## 四、监控和日志

### 4.1 日志配置

编辑 `app/core/logging_config.py`：

```python
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "/var/log/growth-flywheel/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
}
```

### 4.2 健康检查

```bash
# 基础健康检查
curl http://localhost:8000/health

# 详细健康检查
curl http://localhost:8000/health/detailed
```

### 4.3 监控指标

```bash
# 系统指标
curl http://localhost:8000/api/monitoring/metrics

# 性能指标
curl http://localhost:8000/api/monitoring/performance
```

---

## 五、性能优化

### 5.1 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_generation_traces_user_id ON generation_traces(user_id);
CREATE INDEX idx_generation_traces_created_at ON generation_traces(created_at);
CREATE INDEX idx_generation_traces_status ON generation_traces(status);

-- 分析表
ANALYZE generation_traces;
```

### 5.2 Redis 缓存

```python
# 在 .env 中配置
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600  # 1 hour
```

### 5.3 连接池配置

```python
# 在 .env 中配置
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
```

---

## 六、备份和恢复

### 6.1 数据库备份

```bash
# 备份
pg_dump growth_flywheel > backup_$(date +%Y%m%d_%H%M%S).sql

# 恢复
psql growth_flywheel < backup_20260213_120000.sql
```

### 6.2 自动备份脚本

创建 `/usr/local/bin/backup-growth-flywheel.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/growth-flywheel"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
pg_dump growth_flywheel | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# 删除 30 天前的备份
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/db_$DATE.sql.gz"
```

添加到 crontab：

```bash
# 每天凌晨 2 点备份
0 2 * * * /usr/local/bin/backup-growth-flywheel.sh
```

---

## 七、故障排查

### 7.1 常见问题

**问题 1**: 数据库连接失败
```bash
# 检查数据库状态
sudo systemctl status postgresql

# 检查连接
psql -U postgres -h localhost -d growth_flywheel
```

**问题 2**: Redis 连接失败
```bash
# 检查 Redis 状态
sudo systemctl status redis

# 测试连接
redis-cli ping
```

**问题 3**: API 响应慢
```bash
# 检查日志
tail -f /var/log/growth-flywheel/app.log

# 检查系统资源
htop
```

### 7.2 日志查看

```bash
# 应用日志
tail -f /var/log/growth-flywheel/app.log

# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Systemd 日志
journalctl -u growth-flywheel -f
```

---

## 八、安全检查清单

- [ ] JWT_SECRET 已更改（至少 32 字符）
- [ ] 数据库密码强度足够
- [ ] CORS 配置正确
- [ ] API 速率限制已启用
- [ ] SSL/TLS 证书已配置
- [ ] 防火墙规则已设置
- [ ] 日志轮转已配置
- [ ] 备份策略已实施
- [ ] 监控告警已设置
- [ ] 环境变量未泄露

---

## 九、性能基准

### 预期性能指标

| 指标 | 目标值 |
|------|--------|
| API 响应时间 (P50) | < 200ms |
| API 响应时间 (P95) | < 1s |
| 内容生成时间 | < 10s |
| RAG 检索时间 | < 1s |
| 并发请求数 | 100+ |
| 内存使用 | < 2GB |
| CPU 使用 | < 70% |

---

## 十、联系和支持

- **文档**: [README.md](../README.md)
- **API 文档**: http://localhost:8000/docs
- **问题反馈**: GitHub Issues

---

**部署完成后，请运行完整测试**：

```bash
# 运行所有测试
pytest tests/ -v

# 运行集成测试
pytest tests/test_integration.py -v

# 检查系统健康
python verify_system.py
```

祝部署顺利！🚀
