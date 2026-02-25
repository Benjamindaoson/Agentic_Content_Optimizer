# 数据收集系统 - 数据库迁移指南

> 如何创建和应用数据库迁移

**最后更新**: 2026-02-15

---

## 📋 前置条件

确保已安装 Alembic：

```bash
cd backend
pip install alembic
```

---

## 🚀 创建迁移

### 步骤 1: 初始化 Alembic（如果还没有）

```bash
cd backend
alembic init alembic
```

### 步骤 2: 配置 Alembic

编辑 `alembic/env.py`，添加模型导入：

```python
# alembic/env.py

from app.core.database import Base
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog

# 确保 target_metadata 指向 Base.metadata
target_metadata = Base.metadata
```

### 步骤 3: 生成迁移脚本

```bash
# 自动生成迁移（推荐）
alembic revision --autogenerate -m "Add data collection tables"

# 或手动创建迁移
alembic revision -m "Add data collection tables"
```

### 步骤 4: 检查生成的迁移文件

查看 `alembic/versions/` 目录下生成的迁移文件，确认表结构正确。

### 步骤 5: 应用迁移

```bash
# 应用所有待执行的迁移
alembic upgrade head

# 或应用到特定版本
alembic upgrade <revision_id>
```

---

## 🔄 迁移管理

### 查看当前版本

```bash
alembic current
```

### 查看迁移历史

```bash
alembic history
```

### 回滚迁移

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision_id>

# 回滚所有迁移
alembic downgrade base
```

---

## 📝 手动创建表（如果不使用 Alembic）

如果你不想使用 Alembic，可以直接使用 SQLAlchemy 创建表：

```python
# scripts/create_data_collection_tables.py

from app.core.database import engine, Base
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog

def create_tables():
    """创建数据收集相关的表"""
    print("Creating data collection tables...")

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    print("✅ Tables created successfully!")
    print("   - content_generation_logs")
    print("   - user_feedback_logs")
    print("   - ab_test_logs")

if __name__ == "__main__":
    create_tables()
```

运行脚本：

```bash
cd backend
python scripts/create_data_collection_tables.py
```

---

## 🧪 验证表创建

### 方法 1: 使用 psql

```bash
# 连接到数据库
psql -U postgres -d growth_flywheel

# 查看所有表
\dt

# 查看表结构
\d content_generation_logs
\d user_feedback_logs
\d ab_test_logs
```

### 方法 2: 使用 Python

```python
# scripts/verify_tables.py

from sqlalchemy import inspect
from app.core.database import engine

def verify_tables():
    """验证表是否创建成功"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = [
        "content_generation_logs",
        "user_feedback_logs",
        "ab_test_logs"
    ]

    print("Checking tables...")
    for table in required_tables:
        if table in tables:
            print(f"✅ {table} exists")

            # 查看列
            columns = inspector.get_columns(table)
            print(f"   Columns: {len(columns)}")
            for col in columns[:5]:  # 只显示前5列
                print(f"   - {col['name']}: {col['type']}")
        else:
            print(f"❌ {table} does not exist")

    print(f"\nTotal tables in database: {len(tables)}")

if __name__ == "__main__":
    verify_tables()
```

---

## 🔧 常见问题

### Q1: 迁移失败，提示表已存在

**解决方案**：

```bash
# 删除现有表（注意：会丢失数据）
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS content_generation_logs CASCADE;"
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS user_feedback_logs CASCADE;"
psql -U postgres -d growth_flywheel -c "DROP TABLE IF EXISTS ab_test_logs CASCADE;"

# 重新运行迁移
alembic upgrade head
```

### Q2: Alembic 找不到模型

**解决方案**：

确保在 `alembic/env.py` 中正确导入了所有模型：

```python
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog
```

### Q3: 数据库连接失败

**解决方案**：

检查 `.env` 文件中的数据库配置：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/growth_flywheel
```

---

## 📊 迁移后的验证

### 1. 测试插入数据

```python
# scripts/test_data_collection.py

from app.core.database import SessionLocal
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog
import uuid

def test_insert():
    """测试插入数据"""
    db = SessionLocal()

    try:
        # 创建内容生成日志
        content = ContentGenerationLog(
            id=str(uuid.uuid4()),
            user_id="test_user",
            platform="xiaohongshu",
            topic="测试主题",
            model_version="claude-3.5",
            generated_content="这是测试内容",
            quality_score=0.85
        )
        db.add(content)
        db.commit()

        print(f"✅ Content log created: {content.id}")

        # 创建用户反馈
        feedback = UserFeedbackLog(
            id=str(uuid.uuid4()),
            content_id=content.id,
            user_id="test_user",
            event_type="like",
            event_timestamp=1708000000000
        )
        db.add(feedback)
        db.commit()

        print(f"✅ Feedback log created: {feedback.id}")

        # 查询验证
        count = db.query(ContentGenerationLog).count()
        print(f"✅ Total content logs: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_insert()
```

### 2. 测试 API 端点

```bash
# 启动服务器
uvicorn app.main:app --reload

# 测试记录内容生成
curl -X POST http://localhost:8000/api/data-collection/content/log \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "platform": "xiaohongshu",
    "topic": "测试主题",
    "model_version": "claude-3.5",
    "generated_content": "这是测试内容",
    "quality_score": 0.85
  }'

# 测试记录用户反馈
curl -X POST http://localhost:8000/api/data-collection/feedback/log \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "<content_id>",
    "user_id": "test_user",
    "event_type": "like"
  }'

# 查看每日统计
curl http://localhost:8000/api/data-collection/stats/daily
```

---

## 🎉 完成

数据库迁移完成后，你应该能够：

- ✅ 记录每次内容生成
- ✅ 收集用户反馈
- ✅ 追踪 A/B 测试结果
- ✅ 查看统计数据

下一步：集成到现有的内容生成流程中。

---

**相关文档**：
- [DATA_COLLECTION_DESIGN.md](../DATA_COLLECTION_DESIGN.md) - 系统设计
- [FINETUNE_ROADMAP.md](../FINETUNE_ROADMAP.md) - 微调路线图
