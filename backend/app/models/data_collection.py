"""
数据收集系统 - 数据库模型

用于记录内容生成和用户反馈，为后续微调提供数据支持
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ContentGenerationLog(Base):
    """内容生成日志

    记录每次内容生成的完整信息，包括输入参数、生成配置、输出内容等
    """
    __tablename__ = "content_generation_logs"

    # 基础信息
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    session_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    # 输入参数
    platform = Column(String, index=True)  # xiaohongshu, douyin, etc.
    topic = Column(String, index=True)
    persona = Column(String)
    keywords = Column(JSON)  # ["平价", "学生党", ...]
    additional_params = Column(JSON)  # 其他参数

    # 生成配置
    model_version = Column(String, index=True)  # claude-3.5, gpt-4, etc.
    agent_config = Column(JSON)  # Agent 配置
    rag_enabled = Column(Boolean, default=True)
    rl_enabled = Column(Boolean, default=True)

    # 生成内容
    generated_content = Column(Text, nullable=False)
    title = Column(String)
    tags = Column(JSON)
    cover_image_url = Column(String)

    # 生成元数据
    generation_time_ms = Column(Integer)  # 生成耗时（毫秒）
    token_count = Column(Integer)
    cost_usd = Column(Float)

    # 质量评分（系统自动）
    quality_score = Column(Float)  # 0-1
    platform_fit_score = Column(Float)  # 0-1
    viral_potential_score = Column(Float)  # 0-1

    # 聚合指标（定期更新）
    aggregated_metrics = Column(JSON)  # {
    #     "total_views": 100,
    #     "total_likes": 20,
    #     "engagement_rate": 0.2,
    #     "conversion_rate": 0.05
    # }

    # 关系
    feedbacks = relationship("UserFeedbackLog", back_populates="content", cascade="all, delete-orphan")
    ab_tests = relationship("ABTestLog", back_populates="content", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ContentGenerationLog(id={self.id}, platform={self.platform}, topic={self.topic})>"


class UserFeedbackLog(Base):
    """用户反馈日志

    记录用户对生成内容的所有反馈行为
    """
    __tablename__ = "user_feedback_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content_id = Column(String, ForeignKey("content_generation_logs.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    # 用户行为
    event_type = Column(String, index=True, nullable=False)  # view, like, save, share, comment, click, convert
    event_timestamp = Column(BigInteger)  # Unix timestamp (ms)

    # 平台数据（如果有）
    platform_post_id = Column(String, index=True)  # 发布到平台后的 ID
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

    # 关系
    content = relationship("ContentGenerationLog", back_populates="feedbacks")

    def __repr__(self):
        return f"<UserFeedbackLog(id={self.id}, content_id={self.content_id}, event_type={self.event_type})>"


class ABTestLog(Base):
    """A/B 测试日志

    记录 A/B 测试的配置和结果
    """
    __tablename__ = "ab_test_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String, index=True, nullable=False)
    variant_id = Column(String, index=True, nullable=False)  # control, variant_a, variant_b

    content_id = Column(String, ForeignKey("content_generation_logs.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, index=True, nullable=False)

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

    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    # 关系
    content = relationship("ContentGenerationLog", back_populates="ab_tests")

    def __repr__(self):
        return f"<ABTestLog(id={self.id}, experiment_id={self.experiment_id}, variant_id={self.variant_id})>"
