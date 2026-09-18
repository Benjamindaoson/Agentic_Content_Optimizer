"""Database model for durable multimodal production jobs."""

from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from app.core.database import Base


class MultimodalProductionJob(Base):
    """Latest durable checkpoint for one multimodal production job."""

    __tablename__ = "multimodal_production_jobs"

    job_id = Column(String(64), primary_key=True)
    owner_id = Column(String(64), index=True, nullable=True)
    platform = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    stage = Column(String(32), nullable=False, index=True)
    state_json = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
