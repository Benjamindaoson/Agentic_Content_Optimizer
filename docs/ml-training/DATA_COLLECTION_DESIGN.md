# 📊 Growth Flywheel 数据采集系统设计

> 合法合规的用户反馈数据收集方案

**最后更新**: 2026-02-15
**优先级**: 最高（Phase 1 核心任务）

---

## 🎯 设计目标

### 核心目标
```
建立完整的数据闭环，为后续微调提供高质量 reward signal
```

### 关键指标
- 数据覆盖率: 100%（所有生成内容）
- 反馈延迟: < 24 小时
- 数据质量: 人工验证 > 95%
- 合规性: 100%

---

## 📋 数据采集 Schema

### 1. 内容生成记录

```python
class ContentGenerationLog(Base):
    """内容生成日志"""
    __tablename__ = "content_generation_logs"

    # 基础信息
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, index=True)
    session_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 输入参数
    platform = Column(String)  # xiaohongshu, douyin, etc.
    topic = Column(String)
    persona = Column(String)
    keywords = Column(JSON)  # ["平价", "学生党", ...]

    # 生成配置
    model_version = Column(String)  # claude-3.5, gpt-4, etc.
    agent_config = Column(JSON)  # Agent 配置
    rag_enabled = Column(Boolean, default=True)
    rl_enabled = Column(Boolean, default=True)

    # 生成内容
    generated_content = Column(Text)
    title = Column(String)
    tags = Column(JSON)
    cover_image_url = Column(String)

    # 生成元数据
    generation_time_ms = Column(Integer)  # 生成耗时
    token_count = Column(Integer)
    cost_usd = Column(Float)

    # 质量评分（系统自动）
    quality_score = Column(Float)  # 0-1
    platform_fit_score = Column(Float)  # 0-1
    viral_potential_score = Column(Float)  # 0-1
```

### 2. 用户反馈记录

```python
class UserFeedbackLog(Base):
    """用户反馈日志"""
    __tablename__ = "user_feedback_logs"

    id = Column(String, primary_key=True)
    content_id = Column(String, ForeignKey("content_generation_logs.id"), index=True)
    user_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 用户行为
    event_type = Column(String)  # view, like, save, share, comment, click, convert
    event_timestamp = Column(BigInteger)  # Unix timestamp (ms)

    # 平台数据（如果有）
    platform_post_id = Column(String)  # 发布到平台后的 ID
    platform_metrics = Column(JSON)  # {
    #     "impressions": 10000,
    #     "reach": 8500,
    #     "likes": 120,
    #     "comments": 45,
    #     "shares": 30,
    #     "saves": 80,
    #     "click_rate": 0.15,
    #     "engagement_rate": 0.025
    # }

    # 用户评价（可选）
    rating = Column(Integer)  # 1-5 星
    feedback_text = Column(Text)  # 文字反馈
    improvement_suggestions = Column(JSON)  # 改进建议

    # 转化数据（如果有）
    conversion_type = Column(String)  # purchase, signup, download, etc.
    conversion_value = Column(Float)  # 转化价值（元）
```

### 3. A/B 测试记录

```python
class ABTestLog(Base):
    """A/B 测试日志"""
    __tablename__ = "ab_test_logs"

    id = Column(String, primary_key=True)
    experiment_id = Column(String, index=True)
    variant_id = Column(String, index=True)  # control, variant_a, variant_b

    content_id = Column(String, ForeignKey("content_generation_logs.id"))
    user_id = Column(String, index=True)

    # 实验配置
    experiment_config = Column(JSON)  # {
    #     "name": "model_comparison",
    #     "variants": ["claude", "gpt4", "deepseek"],
    #     "traffic_split": [0.33, 0.33, 0.34],
    #     "start_date": "2026-02-15",
    #     "end_date": "2026-02-22"
    # }

    # 结果
    outcome = Column(String)  # success, failure, neutral
    outcome_value = Column(Float)  # 量化结果

    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 🔄 数据采集流程

### 流程图

```
用户请求
    ↓
内容生成（记录 ContentGenerationLog）
    ↓
返回给用户
    ↓
用户使用/发布
    ↓
收集反馈（记录 UserFeedbackLog）
    ↓
    ├─ 实时反馈（点赞、收藏）→ 立即记录
    ├─ 延迟反馈（评论、分享）→ 24小时内记录
    └─ 平台数据（曝光、互动）→ 定期同步（每天）
    ↓
数据聚合与分析
    ↓
生成训练数据
```

---

## 🛠️ 实现方案

### 1. 实时数据采集

**API 端点**:

```python
# backend/app/api.py

@app.post("/api/content/generate")
async def generate_content(
    request: ContentGenerationRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """生成内容并记录"""

    # 1. 生成内容
    start_time = time.time()
    result = await content_generator.generate(request)
    generation_time = (time.time() - start_time) * 1000

    # 2. 记录生成日志
    log = ContentGenerationLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        platform=request.platform,
        topic=request.topic,
        persona=request.persona,
        model_version=result.model_version,
        generated_content=result.content,
        generation_time_ms=generation_time,
        quality_score=result.quality_score,
        # ... 其他字段
    )
    db.add(log)
    db.commit()

    # 3. 返回结果
    return {
        "content_id": log.id,
        "content": result.content,
        "metadata": result.metadata
    }


@app.post("/api/feedback/log")
async def log_feedback(
    feedback: UserFeedbackRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """记录用户反馈"""

    # 验证 content_id 存在
    content = db.query(ContentGenerationLog).filter_by(id=feedback.content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # 记录反馈
    log = UserFeedbackLog(
        id=str(uuid.uuid4()),
        content_id=feedback.content_id,
        user_id=user_id,
        event_type=feedback.event_type,
        event_timestamp=feedback.timestamp,
        platform_metrics=feedback.platform_metrics,
        rating=feedback.rating,
        feedback_text=feedback.feedback_text
    )
    db.add(log)
    db.commit()

    return {"status": "success", "feedback_id": log.id}
```

### 2. 批量数据同步

**定时任务**（Celery）:

```python
# backend/app/tasks/data_sync.py

from celery import Celery
from app.core.database import SessionLocal
from app.data_engineering.platform_sync import PlatformDataSyncer

celery = Celery("tasks", broker="redis://localhost:6379/0")

@celery.task
def sync_platform_data():
    """同步平台数据（每天运行）"""
    db = SessionLocal()
    syncer = PlatformDataSyncer(db)

    # 同步昨天的数据
    yesterday = datetime.now() - timedelta(days=1)
    result = syncer.sync_daily_data(date=yesterday)

    print(f"同步完成: {result['synced_count']} 条记录")
    db.close()


@celery.task
def aggregate_feedback_metrics():
    """聚合反馈指标（每小时运行）"""
    db = SessionLocal()

    # 计算每个内容的聚合指标
    contents = db.query(ContentGenerationLog).filter(
        ContentGenerationLog.created_at >= datetime.now() - timedelta(hours=24)
    ).all()

    for content in contents:
        # 聚合该内容的所有反馈
        feedbacks = db.query(UserFeedbackLog).filter_by(content_id=content.id).all()

        # 计算指标
        metrics = {
            "total_views": sum(1 for f in feedbacks if f.event_type == "view"),
            "total_likes": sum(1 for f in feedbacks if f.event_type == "like"),
            "total_saves": sum(1 for f in feedbacks if f.event_type == "save"),
            "total_shares": sum(1 for f in feedbacks if f.event_type == "share"),
            "total_comments": sum(1 for f in feedbacks if f.event_type == "comment"),
            "total_conversions": sum(1 for f in feedbacks if f.event_type == "convert"),
        }

        # 计算率
        if metrics["total_views"] > 0:
            metrics["engagement_rate"] = (
                metrics["total_likes"] +
                metrics["total_saves"] +
                metrics["total_shares"] +
                metrics["total_comments"]
            ) / metrics["total_views"]

            metrics["conversion_rate"] = metrics["total_conversions"] / metrics["total_views"]

        # 更新内容记录
        content.aggregated_metrics = metrics
        db.commit()

    db.close()


# 配置定时任务
celery.conf.beat_schedule = {
    "sync-platform-data-daily": {
        "task": "app.tasks.data_sync.sync_platform_data",
        "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点
    },
    "aggregate-feedback-hourly": {
        "task": "app.tasks.data_sync.aggregate_feedback_metrics",
        "schedule": crontab(minute=0),  # 每小时
    },
}
```

### 3. 平台数据同步（示例）

```python
# backend/app/data_engineering/platform_sync.py

class PlatformDataSyncer:
    """平台数据同步器"""

    def __init__(self, db: Session):
        self.db = db

    def sync_xiaohongshu_data(self, content_id: str, platform_post_id: str):
        """同步小红书数据（示例）"""

        # 注意：这里需要使用合法的 API 或用户授权的方式获取数据
        # 不要使用爬虫或违反平台规则的方式

        # 方案 1: 用户手动输入（最合规）
        # 方案 2: 使用平台官方 API（如果有）
        # 方案 3: 用户授权后通过 OAuth 获取

        # 这里仅作示例
        try:
            # 假设用户通过前端手动输入了数据
            metrics = {
                "impressions": 10000,
                "likes": 120,
                "comments": 45,
                "shares": 30,
                "saves": 80,
            }

            # 更新反馈日志
            feedback = UserFeedbackLog(
                id=str(uuid.uuid4()),
                content_id=content_id,
                event_type="platform_sync",
                platform_post_id=platform_post_id,
                platform_metrics=metrics,
                created_at=datetime.utcnow()
            )
            self.db.add(feedback)
            self.db.commit()

            return {"status": "success", "metrics": metrics}

        except Exception as e:
            print(f"同步失败: {e}")
            return {"status": "error", "message": str(e)}
```

---

## 🔐 合规性设计

### 1. 数据采集原则

**✅ 合法方式**:
- 用户主动提供的数据
- 用户授权后通过官方 API 获取
- 公开可访问的数据（遵守 robots.txt）
- 平台官方提供的数据导出功能

**❌ 禁止方式**:
- 未经授权的爬虫
- 绕过平台限制的技术手段
- 侵犯用户隐私的数据收集
- 违反平台服务条款的行为

### 2. 用户隐私保护

```python
# 数据脱敏
def anonymize_user_data(data: dict) -> dict:
    """用户数据脱敏"""
    return {
        "user_id": hashlib.sha256(data["user_id"].encode()).hexdigest()[:16],
        "content": data["content"],
        "metrics": data["metrics"],
        # 移除敏感信息
        # "phone": None,
        # "email": None,
    }
```

### 3. 数据使用声明

在用户协议中明确说明：
- 收集哪些数据
- 数据用于什么目的
- 数据如何存储和保护
- 用户如何控制自己的数据

---

## 📊 数据质量保证

### 1. 数据验证

```python
def validate_feedback_data(feedback: dict) -> bool:
    """验证反馈数据质量"""

    # 基础验证
    if not feedback.get("content_id"):
        return False

    if not feedback.get("event_type"):
        return False

    # 数值合理性验证
    if feedback.get("rating") and not (1 <= feedback["rating"] <= 5):
        return False

    # 时间戳验证
    if feedback.get("event_timestamp"):
        now = int(time.time() * 1000)
        if feedback["event_timestamp"] > now:
            return False  # 未来时间

        if feedback["event_timestamp"] < now - 30 * 24 * 3600 * 1000:
            return False  # 超过 30 天

    return True
```

### 2. 异常检测

```python
def detect_anomalies(content_id: str, db: Session) -> List[str]:
    """检测异常数据"""

    anomalies = []

    # 获取该内容的所有反馈
    feedbacks = db.query(UserFeedbackLog).filter_by(content_id=content_id).all()

    # 检测 1: 短时间内大量反馈（可能是刷量）
    if len(feedbacks) > 100:
        time_span = (feedbacks[-1].created_at - feedbacks[0].created_at).total_seconds()
        if time_span < 60:  # 1 分钟内 100+ 反馈
            anomalies.append("suspicious_high_frequency")

    # 检测 2: 同一用户重复反馈
    user_counts = {}
    for f in feedbacks:
        user_counts[f.user_id] = user_counts.get(f.user_id, 0) + 1

    if max(user_counts.values()) > 10:
        anomalies.append("suspicious_repeated_user")

    # 检测 3: 互动率异常高（可能是假数据）
    likes = sum(1 for f in feedbacks if f.event_type == "like")
    views = sum(1 for f in feedbacks if f.event_type == "view")

    if views > 0 and likes / views > 0.5:  # 点赞率 > 50%
        anomalies.append("suspicious_high_engagement")

    return anomalies
```

---

## 🎯 数据导出（用于训练）

### 1. 构建 DPO 偏好对

```python
# backend/app/data_engineering/preference_builder.py

class PreferencePairBuilder:
    """构建 DPO 偏好对"""

    def __init__(self, db: Session):
        self.db = db

    def build_preference_pairs(
        self,
        min_engagement_rate: float = 0.05,
        max_engagement_rate: float = 0.01,
        days: int = 7
    ) -> List[dict]:
        """从历史数据构建偏好对"""

        # 获取最近 N 天的内容
        start_date = datetime.now() - timedelta(days=days)
        contents = self.db.query(ContentGenerationLog).filter(
            ContentGenerationLog.created_at >= start_date
        ).all()

        # 按 topic 分组
        topic_groups = {}
        for content in contents:
            if content.topic not in topic_groups:
                topic_groups[content.topic] = []
            topic_groups[content.topic].append(content)

        # 构建偏好对
        preference_pairs = []

        for topic, group in topic_groups.items():
            # 计算每个内容的 engagement_rate
            for content in group:
                feedbacks = self.db.query(UserFeedbackLog).filter_by(
                    content_id=content.id
                ).all()

                views = sum(1 for f in feedbacks if f.event_type == "view")
                engagements = sum(1 for f in feedbacks if f.event_type in ["like", "save", "share", "comment"])

                content.engagement_rate = engagements / views if views > 0 else 0

            # 找出高互动和低互动的内容
            high_engagement = [c for c in group if c.engagement_rate >= min_engagement_rate]
            low_engagement = [c for c in group if c.engagement_rate <= max_engagement_rate]

            # 构建偏好对
            for high in high_engagement:
                for low in low_engagement:
                    preference_pairs.append({
                        "prompt": f"为{high.platform}平台生成关于{topic}的内容，目标用户是{high.persona}",
                        "chosen": high.generated_content,
                        "rejected": low.generated_content,
                        "score": high.engagement_rate - low.engagement_rate,
                        "metadata": {
                            "chosen_id": high.id,
                            "rejected_id": low.id,
                            "chosen_engagement": high.engagement_rate,
                            "rejected_engagement": low.engagement_rate,
                        }
                    })

        return preference_pairs

    def export_to_jsonl(self, pairs: List[dict], output_path: str):
        """导出为 JSONL 格式"""
        with open(output_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        print(f"✅ 导出 {len(pairs)} 个偏好对到 {output_path}")
```

### 2. 导出命令

```bash
# 导出最近 7 天的偏好对
python -c "
from app.data_engineering.preference_builder import PreferencePairBuilder
from app.core.database import SessionLocal

db = SessionLocal()
builder = PreferencePairBuilder(db)

pairs = builder.build_preference_pairs(days=7)
builder.export_to_jsonl(pairs, './data/preference_pairs/pairs_20260215.jsonl')

db.close()
"
```

---

## 📈 监控与报告

### 1. 数据采集监控

```python
# 每日数据报告
def generate_daily_report(date: datetime) -> dict:
    """生成每日数据报告"""
    db = SessionLocal()

    # 统计当天的数据
    start = date.replace(hour=0, minute=0, second=0)
    end = start + timedelta(days=1)

    contents = db.query(ContentGenerationLog).filter(
        ContentGenerationLog.created_at >= start,
        ContentGenerationLog.created_at < end
    ).all()

    feedbacks = db.query(UserFeedbackLog).filter(
        UserFeedbackLog.created_at >= start,
        UserFeedbackLog.created_at < end
    ).all()

    report = {
        "date": date.strftime("%Y-%m-%d"),
        "total_contents": len(contents),
        "total_feedbacks": len(feedbacks),
        "feedback_rate": len(feedbacks) / len(contents) if contents else 0,

        "by_platform": {},
        "by_event_type": {},

        "avg_engagement_rate": 0,
        "avg_conversion_rate": 0,
    }

    # 按平台统计
    for content in contents:
        platform = content.platform
        if platform not in report["by_platform"]:
            report["by_platform"][platform] = 0
        report["by_platform"][platform] += 1

    # 按事件类型统计
    for feedback in feedbacks:
        event_type = feedback.event_type
        if event_type not in report["by_event_type"]:
            report["by_event_type"][event_type] = 0
        report["by_event_type"][event_type] += 1

    db.close()
    return report
```

---

## 🎉 总结

### 核心原则

```
1. 合法合规 > 数据数量
2. 用户授权 > 技术手段
3. 数据质量 > 数据速度
```

### 实施步骤

1. **Week 1-2**: 实现基础数据采集（ContentGenerationLog + UserFeedbackLog）
2. **Week 3-4**: 实现反馈收集 API 和前端集成
3. **Week 5-6**: 实现定时任务和数据聚合
4. **Week 7-8**: 实现数据导出和偏好对构建
5. **Week 9+**: 持续优化和监控

### 成功标准

- ✅ 100% 内容生成都有记录
- ✅ 80%+ 内容有用户反馈
- ✅ 数据质量验证通过率 > 95%
- ✅ 零合规问题

---

**最后更新**: 2026-02-15
**下一步**: 实现 ContentGenerationLog 和 UserFeedbackLog 数据库表
