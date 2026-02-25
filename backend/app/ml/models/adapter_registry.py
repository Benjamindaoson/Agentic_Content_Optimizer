"""
Adapter Registry

管理所有训练的 adapters
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Session
import os
import json
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)


class AdapterRecord(Base):
    """Adapter 记录"""

    __tablename__ = "adapter_registry"

    id = Column(String, primary_key=True)
    adapter_name = Column(String, unique=True, index=True, nullable=False)
    adapter_type = Column(String, index=True, nullable=False)  # sft, dpo
    base_model = Column(String, nullable=False)
    adapter_path = Column(String, nullable=False)

    # 平台信息
    platform = Column(String, index=True)
    persona = Column(String, index=True)
    niche = Column(String, index=True)

    # 训练信息
    training_config = Column(JSON)
    training_samples = Column(Integer)
    training_epochs = Column(Integer)
    training_time_seconds = Column(Float)

    # 评估指标
    eval_metrics = Column(JSON)

    # 状态
    status = Column(String, index=True, default="active")  # active, archived, deprecated
    is_default = Column(Boolean, default=False)

    # 元数据
    adapter_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdapterRegistry:
    """Adapter 注册表"""

    def __init__(self, db: Session):
        self.db = db

    def register(
        self,
        adapter_name: str,
        adapter_type: str,
        base_model: str,
        adapter_path: str,
        platform: Optional[str] = None,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        training_config: Optional[Dict[str, Any]] = None,
        training_samples: Optional[int] = None,
        training_epochs: Optional[int] = None,
        training_time_seconds: Optional[float] = None,
        eval_metrics: Optional[Dict[str, Any]] = None,
        adapter_metadata: Optional[Dict[str, Any]] = None,
    ) -> AdapterRecord:
        """注册新的 adapter"""
        import uuid

        logger.info(f"注册 adapter: {adapter_name}")

        # 检查是否已存在
        existing = self.db.query(AdapterRecord).filter_by(adapter_name=adapter_name).first()
        if existing:
            logger.warning(f"Adapter {adapter_name} 已存在，更新记录")
            existing.adapter_type = adapter_type
            existing.base_model = base_model
            existing.adapter_path = adapter_path
            existing.platform = platform
            existing.persona = persona
            existing.niche = niche
            existing.training_config = training_config
            existing.training_samples = training_samples
            existing.training_epochs = training_epochs
            existing.training_time_seconds = training_time_seconds
            existing.eval_metrics = eval_metrics
            existing.adapter_metadata = adapter_metadata
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # 创建新记录
        record = AdapterRecord(
            id=str(uuid.uuid4()),
            adapter_name=adapter_name,
            adapter_type=adapter_type,
            base_model=base_model,
            adapter_path=adapter_path,
            platform=platform,
            persona=persona,
            niche=niche,
            training_config=training_config,
            training_samples=training_samples,
            training_epochs=training_epochs,
            training_time_seconds=training_time_seconds,
            eval_metrics=eval_metrics,
            adapter_metadata=adapter_metadata,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(f"Adapter {adapter_name} 注册成功")
        return record

    def get(self, adapter_name: str) -> Optional[AdapterRecord]:
        """获取 adapter 记录"""
        return self.db.query(AdapterRecord).filter_by(adapter_name=adapter_name).first()

    def list(
        self,
        adapter_type: Optional[str] = None,
        platform: Optional[str] = None,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        status: str = "active",
    ) -> List[AdapterRecord]:
        """列出 adapters"""
        query = self.db.query(AdapterRecord).filter_by(status=status)

        if adapter_type:
            query = query.filter_by(adapter_type=adapter_type)
        if platform:
            query = query.filter_by(platform=platform)
        if persona:
            query = query.filter_by(persona=persona)
        if niche:
            query = query.filter_by(niche=niche)

        return query.order_by(AdapterRecord.created_at.desc()).all()

    def get_default(
        self,
        platform: Optional[str] = None,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
    ) -> Optional[AdapterRecord]:
        """获取默认 adapter"""
        query = self.db.query(AdapterRecord).filter_by(is_default=True, status="active")

        if platform:
            query = query.filter_by(platform=platform)
        if persona:
            query = query.filter_by(persona=persona)
        if niche:
            query = query.filter_by(niche=niche)

        return query.first()

    def set_default(self, adapter_name: str):
        """设置默认 adapter"""
        adapter = self.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        # 取消同平台/人设/领域的其他默认 adapter
        self.db.query(AdapterRecord).filter_by(
            platform=adapter.platform,
            persona=adapter.persona,
            niche=adapter.niche,
            is_default=True,
        ).update({"is_default": False})

        # 设置新的默认 adapter
        adapter.is_default = True
        self.db.commit()

        logger.info(f"Adapter {adapter_name} 设置为默认")

    def archive(self, adapter_name: str):
        """归档 adapter"""
        adapter = self.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        adapter.status = "archived"
        adapter.is_default = False
        self.db.commit()

        logger.info(f"Adapter {adapter_name} 已归档")

    def delete(self, adapter_name: str, delete_files: bool = False):
        """删除 adapter"""
        adapter = self.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        # 删除文件
        if delete_files and os.path.exists(adapter.adapter_path):
            import shutil
            shutil.rmtree(adapter.adapter_path)
            logger.info(f"删除 adapter 文件: {adapter.adapter_path}")

        # 删除记录
        self.db.delete(adapter)
        self.db.commit()

        logger.info(f"Adapter {adapter_name} 已删除")

    def update_metrics(self, adapter_name: str, eval_metrics: Dict[str, Any]):
        """更新评估指标"""
        adapter = self.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        adapter.eval_metrics = eval_metrics
        adapter.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Adapter {adapter_name} 指标已更新")
