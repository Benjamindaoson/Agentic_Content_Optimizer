"""Prompt 版本管理模型。"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class PromptTemplate(Base):
    """Prompt 模板版本表。"""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), index=True, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    channel = Column(String(32), nullable=False, default="default")
    template = Column(Text, nullable=False)
    description = Column(String(512), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(String(128), nullable=True, default="system")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

