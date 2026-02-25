"""
Generation Trace 数据库模型
Database Model for Generation Traces
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class GenerationTraceModel(Base):
    """生成追踪记录表"""

    __tablename__ = "generation_traces"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=True)

    # 追踪数据（JSON 格式）
    data = Column(JSON, nullable=False)

    # 元数据
    status = Column(String(32), default="completed", index=True)
    duration = Column(Integer, nullable=True)  # 毫秒

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<GenerationTrace(trace_id={self.trace_id}, status={self.status})>"
