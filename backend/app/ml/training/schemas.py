"""
Training Data Schemas

定义训练数据的核心 schema
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


# ==================== SQLAlchemy Models ====================

class GenerationTrace(Base):
    """内容生成追踪表

    记录每次内容生成的完整信息，用于训练数据构建
    """
    __tablename__ = "generation_traces"

    id = Column(String, primary_key=True)

    # 平台与场景
    platform = Column(String, index=True, nullable=False)  # xhs, douyin
    persona = Column(String, index=True)  # 学生党, 打工人, 宝妈
    niche = Column(String, index=True)  # 护肤, 穿搭, 家电
    topic = Column(String, nullable=False)

    # 输入
    prompt = Column(Text, nullable=False)
    system_prompt = Column(Text)
    constraints = Column(JSON)  # 约束条件
    retrieved_context = Column(JSON)  # RAG 检索的上下文

    # 输出
    output = Column(Text, nullable=False)
    title = Column(String)
    tags = Column(JSON)
    cover_text = Column(String)
    cta = Column(String)  # Call to action

    # 模型与策略
    policy_id = Column(String, index=True)
    model_id = Column(String, index=True)
    adapter_id = Column(String, index=True)

    # 元数据
    generation_time_ms = Column(Integer)
    token_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 关系
    outcomes = relationship("Outcome", back_populates="trace", cascade="all, delete-orphan")


class Outcome(Base):
    """内容效果追踪表

    记录内容发布后的真实效果指标
    """
    __tablename__ = "outcomes"

    id = Column(String, primary_key=True)
    trace_id = Column(String, ForeignKey("generation_traces.id", ondelete="CASCADE"), index=True, nullable=False)

    # 曝光与点击
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    click_rate = Column(Float, default=0.0)

    # 停留与完读
    read_time_avg = Column(Float, default=0.0)  # 平均停留时间（秒）
    completion_rate = Column(Float, default=0.0)  # 完读率

    # 互动
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    saves = Column(Integer, default=0)  # 收藏
    shares = Column(Integer, default=0)

    # 转化
    follows = Column(Integer, default=0)
    dms = Column(Integer, default=0)  # 私信
    purchases = Column(Integer, default=0)

    # 综合指标
    engagement_score = Column(Float, default=0.0)  # 综合互动分

    # 时间窗口
    time_bucket = Column(String, index=True)  # 1h, 6h, 24h, 7d
    measured_at = Column(DateTime, default=datetime.utcnow)

    # RL 闭环同步状态
    rl_synced = Column(Integer, default=0)  # 0=未同步, 1=已同步
    rl_synced_at = Column(DateTime, nullable=True)

    # 关系
    trace = relationship("GenerationTrace", back_populates="outcomes")


# ==================== Pydantic Models ====================

class GenerationTraceCreate(BaseModel):
    """创建 GenerationTrace 的请求"""
    platform: str = Field(..., description="平台: xhs, douyin")
    persona: Optional[str] = Field(None, description="人设")
    niche: Optional[str] = Field(None, description="领域")
    topic: str = Field(..., description="主题")

    prompt: str = Field(..., description="用户 prompt")
    system_prompt: Optional[str] = Field(None, description="系统 prompt")
    constraints: Optional[Dict[str, Any]] = Field(None, description="约束条件")
    retrieved_context: Optional[List[Dict[str, Any]]] = Field(None, description="RAG 上下文")

    output: str = Field(..., description="生成的内容")
    title: Optional[str] = Field(None, description="标题")
    tags: Optional[List[str]] = Field(None, description="标签")
    cover_text: Optional[str] = Field(None, description="封面文案")
    cta: Optional[str] = Field(None, description="行动号召")

    policy_id: Optional[str] = Field(None, description="策略 ID")
    model_id: Optional[str] = Field(None, description="模型 ID")
    adapter_id: Optional[str] = Field(None, description="Adapter ID")

    generation_time_ms: Optional[int] = Field(None, description="生成耗时（毫秒）")
    token_count: Optional[int] = Field(None, description="token 数量")


class OutcomeCreate(BaseModel):
    """创建 Outcome 的请求"""
    trace_id: str = Field(..., description="GenerationTrace ID")

    impressions: int = Field(0, description="曝光数")
    clicks: int = Field(0, description="点击数")

    read_time_avg: float = Field(0.0, description="平均停留时间（秒）")
    completion_rate: float = Field(0.0, description="完读率")

    likes: int = Field(0, description="点赞数")
    comments: int = Field(0, description="评论数")
    saves: int = Field(0, description="收藏数")
    shares: int = Field(0, description="分享数")

    follows: int = Field(0, description="关注数")
    dms: int = Field(0, description="私信数")
    purchases: int = Field(0, description="购买数")

    time_bucket: str = Field("24h", description="时间窗口")


class SFTDataSample(BaseModel):
    """SFT 训练样本"""
    messages: List[Dict[str, str]] = Field(..., description="对话消息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class DPODataSample(BaseModel):
    """DPO 训练样本"""
    prompt: str = Field(..., description="输入 prompt")
    chosen: str = Field(..., description="更好的输出")
    rejected: str = Field(..., description="较差的输出")
    score_diff: float = Field(..., description="分数差异")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class TrainingDataset(BaseModel):
    """训练数据集"""
    dataset_type: str = Field(..., description="数据集类型: sft, dpo")
    platform: str = Field(..., description="平台")
    samples: List[Dict[str, Any]] = Field(..., description="样本列表")
    total_samples: int = Field(..., description="总样本数")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
