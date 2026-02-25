# 🚀 数据收集系统 - 快速开始

> 5 分钟快速部署数据收集系统

**最后更新**: 2026-02-15

---

## 📋 前置条件

- ✅ PostgreSQL 数据库已安装并运行
- ✅ Python 3.10+ 环境
- ✅ 已安装项目依赖 (`pip install -r requirements.txt`)

---

## 🚀 快速部署（3 步）

### 步骤 1: 创建数据库表（1 分钟）

```bash
cd backend

# 方法 1: 使用脚本（推荐）
python scripts/create_data_collection_tables.py

# 方法 2: 使用 Alembic
alembic revision --autogenerate -m "Add data collection tables"
alembic upgrade head
```

**预期输出**:
```
================================================================================
📊 创建数据收集系统表
================================================================================

🔄 正在创建表...

✅ 表创建成功！
   - content_generation_logs (内容生成日志)
   - user_feedback_logs (用户反馈日志)
   - ab_test_logs (A/B 测试日志)
```

### 步骤 2: 测试数据插入（1 分钟）

```bash
python scripts/test_data_collection.py
```

**预期输出**:
```
================================================================================
🧪 数据收集系统测试
================================================================================

📝 测试内容生成日志
✅ 内容生成日志创建成功
   ID: 550e8400-e29b-41d4-a716-446655440000
   平台: xiaohongshu
   主题: AI 写作工具推荐
   模型: claude-3.5-sonnet
   质量评分: 0.85

👍 测试用户反馈日志
✅ 用户反馈日志创建成功
   创建了 4 条反馈记录

✅ 所有测试完成！
```

### 步骤 3: 启动 API 服务（1 分钟）

```bash
# 确保 API 路由已注册
# 编辑 app/main.py，添加：
# from app.api_data_collection import router as data_collection_router
# app.include_router(data_collection_router)

# 启动服务
uvicorn app.main:app --reload
```

访问 API 文档: http://localhost:8000/docs

---

## 🧪 测试 API 端点

### 1. 记录内容生成

```bash
curl -X POST http://localhost:8000/api/data-collection/content/log \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "platform": "xiaohongshu",
    "topic": "AI 写作工具",
    "persona": "学生党",
    "keywords": ["AI", "写作", "效率"],
    "model_version": "claude-3.5-sonnet",
    "generated_content": "🤖 学生党必备！这款 AI 写作工具太好用了...",
    "quality_score": 0.85
  }'
```

**预期响应**:
```json
{
  "status": "success",
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "内容生成日志已记录"
}
```

### 2. 记录用户反馈

```bash
curl -X POST http://localhost:8000/api/data-collection/feedback/log \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user_123",
    "event_type": "like",
    "rating": 5,
    "feedback_text": "内容很有帮助！"
  }'
```

**预期响应**:
```json
{
  "status": "success",
  "feedback_id": "660e8400-e29b-41d4-a716-446655440001",
  "message": "用户反馈已记录"
}
```

### 3. 查看每日统计

```bash
curl http://localhost:8000/api/data-collection/stats/daily
```

**预期响应**:
```json
{
  "date": "2026-02-15",
  "total_contents": 10,
  "total_feedbacks": 45,
  "feedback_rate": 4.5,
  "by_platform": {
    "xiaohongshu": 6,
    "douyin": 4
  },
  "by_event_type": {
    "view": 10,
    "like": 20,
    "save": 10,
    "share": 5
  }
}
```

---

## 🔗 集成到现有系统

### 在内容生成流程中添加日志记录

编辑 `app/api.py` 或相应的内容生成端点：

```python
from app.api_data_collection import ContentGenerationLogRequest
from app.models.data_collection import ContentGenerationLog
import time
import uuid

@app.post("/api/generate/content")
async def generate_content(
    request: ContentGenerationRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """生成内容并记录日志"""

    # 1. 生成内容
    start_time = time.time()
    result = await content_generator.generate(request)
    generation_time = int((time.time() - start_time) * 1000)

    # 2. 记录生成日志
    log = ContentGenerationLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        platform=request.platform,
        topic=request.topic,
        persona=request.persona,
        keywords=request.keywords,
        model_version=result.model_version,
        generated_content=result.content,
        generation_time_ms=generation_time,
        quality_score=result.quality_score,
        platform_fit_score=result.platform_fit_score,
        viral_potential_score=result.viral_potential_score,
    )
    db.add(log)
    db.commit()

    # 3. 返回结果（包含 content_id）
    return {
        "content_id": log.id,
        "content": result.content,
        "metadata": result.metadata
    }
```

### 在前端添加反馈收集

```typescript
// frontend/src/api/dataCollection.ts

export async function logUserFeedback(
  contentId: string,
  eventType: 'view' | 'like' | 'save' | 'share' | 'comment' | 'click' | 'convert',
  additionalData?: {
    rating?: number;
    feedbackText?: string;
    platformMetrics?: any;
  }
) {
  const response = await fetch('/api/data-collection/feedback/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content_id: contentId,
      user_id: getCurrentUserId(),
      event_type: eventType,
      event_timestamp: Date.now(),
      ...additionalData
    })
  });

  return response.json();
}

// 使用示例
// 用户点赞时
await logUserFeedback(contentId, 'like', { rating: 5 });

// 用户收藏时
await logUserFeedback(contentId, 'save');

// 用户分享时
await logUserFeedback(contentId, 'share');
```

---

## 📊 数据查看

### 使用 psql 查看数据

```bash
# 连接数据库
psql -U postgres -d growth_flywheel

# 查看最近的内容生成
SELECT id, platform, topic, model_version, quality_score, created_at
FROM content_generation_logs
ORDER BY created_at DESC
LIMIT 10;

# 查看最近的用户反馈
SELECT content_id, user_id, event_type, created_at
FROM user_feedback_logs
ORDER BY created_at DESC
LIMIT 10;

# 统计每个平台的内容数量
SELECT platform, COUNT(*) as count
FROM content_generation_logs
GROUP BY platform;

# 统计每种事件类型的数量
SELECT event_type, COUNT(*) as count
FROM user_feedback_logs
GROUP BY event_type;
```

---

## 🎯 下一步

### 1. 部署定时任务（Celery）

```bash
# 安装 Celery 和 Redis
pip install celery redis

# 启动 Redis
redis-server

# 启动 Celery Worker
celery -A app.tasks worker --loglevel=info

# 启动 Celery Beat（定时任务）
celery -A app.tasks beat --loglevel=info
```

### 2. 配置数据聚合任务

参考 [DATA_COLLECTION_DESIGN.md](../DATA_COLLECTION_DESIGN.md) 中的定时任务配置。

### 3. 开始收集真实数据

- 在生产环境部署数据收集系统
- 监控数据收集质量
- 定期查看统计报告

### 4. 准备微调（3-6 个月后）

当收集到足够的数据（10,000+ 条反馈）后：
- 使用 `PreferencePairBuilder` 构建偏好对
- 开始 Phase 2: Style SFT 训练
- 参考 [FINETUNE_ROADMAP.md](../FINETUNE_ROADMAP.md)

---

## 🔧 故障排查

### 问题 1: 表创建失败

**错误**: `relation "content_generation_logs" already exists`

**解决方案**:
```bash
# 删除现有表（注意：会丢失数据）
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS content_generation_logs CASCADE;"
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS user_feedback_logs CASCADE;"
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS ab_test_logs CASCADE;"

# 重新创建
python scripts/create_data_collection_tables.py
```

### 问题 2: API 端点 404

**解决方案**:

确保在 `app/main.py` 中注册了路由：

```python
from app.api_data_collection import router as data_collection_router

app.include_router(data_collection_router)
```

### 问题 3: 数据库连接失败

**解决方案**:

检查 `.env` 文件中的数据库配置：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/growth_flywheel
```

---

## 📚 相关文档

- [DATA_COLLECTION_DESIGN.md](../DATA_COLLECTION_DESIGN.md) - 完整系统设计
- [DATABASE_MIGRATION_GUIDE.md](./DATABASE_MIGRATION_GUIDE.md) - 数据库迁移指南
- [FINETUNE_ROADMAP.md](../FINETUNE_ROADMAP.md) - 微调路线图

---

**最后更新**: 2026-02-15
**状态**: ✅ 就绪，可以开始收集数据
