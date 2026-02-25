"""
线上日志采集系统

功能：
1. 记录用户对生成内容的反馈
2. 采集必需字段（user_id, item_id, prompt, generated_content, event_type等）
3. 支持批量写入和异步处理
4. 数据验证和清洗
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from app.core.database import Base

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    EXPOSURE = "exposure"      # 曝光
    CLICK = "click"            # 点击
    LIKE = "like"              # 点赞
    DISLIKE = "dislike"        # 点踩
    SHARE = "share"            # 分享
    COLLECT = "collect"        # 收藏
    COMMENT = "comment"        # 评论
    HIDE = "hide"              # 隐藏
    REPORT = "report"          # 举报


class UserFeedbackLog(Base):
    """用户反馈日志表"""
    __tablename__ = "user_feedback_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 用户和内容标识
    user_id = Column(String(64), nullable=False, index=True)
    item_id = Column(String(64), nullable=False, index=True)
    generation_id = Column(String(64), nullable=True, index=True)

    # 请求上下文
    prompt = Column(Text, nullable=False)
    topic = Column(String(256), nullable=True)
    platform = Column(String(32), nullable=True)

    # 生成结果
    generated_content = Column(Text, nullable=False)
    model_version = Column(String(64), nullable=False, index=True)
    pattern_id = Column(String(64), nullable=True, index=True)

    # 行为数据
    event_type = Column(String(32), nullable=False, index=True)
    event_timestamp = Column(Integer, nullable=False, index=True)  # Unix 时间戳（毫秒）
    event_scene = Column(String(64), nullable=True)

    # 反馈强度
    feedback_value = Column(Float, nullable=True)  # 连续评分（如星级）

    # 设备信息
    device_os = Column(String(32), nullable=True)
    browser = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)

    # 额外元数据
    metadata = Column(JSON, nullable=True)

    # 创建时间
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # 索引
    __table_args__ = (
        Index('idx_user_event', 'user_id', 'event_type'),
        Index('idx_model_event', 'model_version', 'event_type'),
        Index('idx_timestamp', 'event_timestamp'),
    )


@dataclass
class FeedbackEvent:
    """反馈事件数据类"""
    user_id: str
    item_id: str
    prompt: str
    generated_content: str
    model_version: str
    event_type: str
    event_timestamp: int

    # 可选字段
    generation_id: Optional[str] = None
    topic: Optional[str] = None
    platform: Optional[str] = None
    pattern_id: Optional[str] = None
    event_scene: Optional[str] = None
    feedback_value: Optional[float] = None
    device_os: Optional[str] = None
    browser: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def validate(self) -> bool:
        """验证数据有效性"""
        # 必需字段检查
        if not all([
            self.user_id,
            self.item_id,
            self.prompt,
            self.generated_content,
            self.model_version,
            self.event_type
        ]):
            return False

        # 事件类型检查
        if self.event_type not in [e.value for e in EventType]:
            return False

        # 长度检查
        if len(self.prompt) < 1 or len(self.prompt) > 10000:
            return False

        if len(self.generated_content) < 1 or len(self.generated_content) > 50000:
            return False

        return True


class FeedbackCollector:
    """反馈采集器"""

    def __init__(self, db: Session, batch_size: int = 100):
        """初始化采集器

        Args:
            db: 数据库会话
            batch_size: 批量写入大小
        """
        self.db = db
        self.batch_size = batch_size
        self._buffer: List[FeedbackEvent] = []
        self._lock = asyncio.Lock()

    async def log_event(self, event: FeedbackEvent) -> bool:
        """记录单个事件

        Args:
            event: 反馈事件

        Returns:
            是否成功
        """
        # 验证数据
        if not event.validate():
            logger.warning(f"Invalid feedback event: {event}")
            return False

        # 添加到缓冲区
        async with self._lock:
            self._buffer.append(event)

            # 达到批量大小时写入
            if len(self._buffer) >= self.batch_size:
                await self._flush()

        return True

    async def log_batch(self, events: List[FeedbackEvent]) -> int:
        """批量记录事件

        Args:
            events: 事件列表

        Returns:
            成功记录的数量
        """
        success_count = 0

        for event in events:
            if await self.log_event(event):
                success_count += 1

        return success_count

    async def _flush(self):
        """刷新缓冲区到数据库"""
        if not self._buffer:
            return

        try:
            # 转换为数据库模型
            logs = []
            for event in self._buffer:
                log = UserFeedbackLog(**asdict(event))
                logs.append(log)

            # 批量插入
            self.db.bulk_save_objects(logs)
            self.db.commit()

            logger.info(f"Flushed {len(logs)} feedback events to database")

            # 清空缓冲区
            self._buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush feedback events: {e}")
            self.db.rollback()

    async def flush(self):
        """手动刷新缓冲区"""
        async with self._lock:
            await self._flush()

    def get_reward_score(self, event_type: str) -> float:
        """将事件类型映射为奖励分数

        Args:
            event_type: 事件类型

        Returns:
            奖励分数
        """
        mapping = {
            EventType.LIKE.value: 1.0,
            EventType.SHARE.value: 1.0,
            EventType.COLLECT.value: 1.0,
            EventType.COMMENT.value: 0.8,
            EventType.CLICK.value: 0.5,
            EventType.EXPOSURE.value: 0.0,
            EventType.DISLIKE.value: -1.0,
            EventType.HIDE.value: -1.0,
            EventType.REPORT.value: -2.0
        }
        return mapping.get(event_type, 0.0)


# 全局采集器实例
_collector: Optional[FeedbackCollector] = None


def get_feedback_collector(db: Session) -> FeedbackCollector:
    """获取全局采集器实例

    Args:
        db: 数据库会话

    Returns:
        采集器实例
    """
    global _collector
    if _collector is None:
        _collector = FeedbackCollector(db=db)
    return _collector


# FastAPI 集成示例
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

@router.post("/log")
async def log_feedback(
    event: FeedbackEvent,
    db: Session = Depends(get_db)
):
    '''记录用户反馈'''
    collector = get_feedback_collector(db)
    success = await collector.log_event(event)

    if success:
        return {"status": "success", "message": "Feedback logged"}
    else:
        return {"status": "error", "message": "Invalid feedback data"}

@router.post("/log-batch")
async def log_feedback_batch(
    events: List[FeedbackEvent],
    db: Session = Depends(get_db)
):
    '''批量记录用户反馈'''
    collector = get_feedback_collector(db)
    success_count = await collector.log_batch(events)

    return {
        "status": "success",
        "total": len(events),
        "success": success_count,
        "failed": len(events) - success_count
    }
"""
