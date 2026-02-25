"""
版本管理服务

用于管理 Prompt、模板、模型的版本，支持回滚和可复现
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import Session
from app.core.database import Base

logger = logging.getLogger(__name__)


class VersionStatus(str, Enum):
    """版本状态"""
    DRAFT = 'draft'  # 草稿
    TESTING = 'testing'  # 测试中
    ACTIVE = 'active'  # 激活
    DEPRECATED = 'deprecated'  # 已弃用
    ARCHIVED = 'archived'  # 已归档


class VersionType(str, Enum):
    """版本类型"""
    PROMPT = 'prompt'  # Prompt 版本
    TEMPLATE = 'template'  # 模板版本
    MODEL = 'model'  # 模型版本
    POLICY = 'policy'  # 策略版本


# ==================== 数据库模型 ====================

class Version(Base):
    """版本表"""
    __tablename__ = 'versions'

    version_id = Column(String(64), primary_key=True, comment='版本ID')
    version_type = Column(SQLEnum(VersionType), nullable=False, comment='版本类型')
    version_name = Column(String(128), nullable=False, comment='版本名称')
    version_number = Column(String(32), nullable=False, comment='版本号（如 v1.0.0）')

    # 版本内容
    content = Column(JSON, nullable=False, comment='版本内容')
    content_hash = Column(String(64), nullable=False, comment='内容哈希')

    # 版本状态
    status = Column(SQLEnum(VersionStatus), default=VersionStatus.DRAFT, comment='版本状态')
    is_default = Column(Boolean, default=False, comment='是否默认版本')

    # 性能指标
    performance_metrics = Column(JSON, comment='性能指标')
    usage_count = Column(Integer, default=0, comment='使用次数')

    # 元数据
    created_by = Column(String(64), comment='创建人')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    activated_at = Column(DateTime, comment='激活时间')
    deprecated_at = Column(DateTime, comment='弃用时间')
    metadata = Column(JSON, comment='其他元数据')


class VersionUsage(Base):
    """版本使用记录表"""
    __tablename__ = 'version_usage'

    usage_id = Column(String(64), primary_key=True, comment='使用ID')
    version_id = Column(String(64), nullable=False, comment='版本ID')

    # 使用信息
    generation_id = Column(String(64), comment='生成ID')
    task_id = Column(String(64), comment='任务ID')
    note_id = Column(String(64), comment='笔记ID')

    # 结果信息
    success = Column(Boolean, comment='是否成功')
    result_metrics = Column(JSON, comment='结果指标')

    # 时间信息
    used_at = Column(DateTime, default=datetime.now, comment='使用时间')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


class VersionRollback(Base):
    """版本回滚记录表"""
    __tablename__ = 'version_rollbacks'

    rollback_id = Column(String(64), primary_key=True, comment='回滚ID')

    # 回滚信息
    from_version_id = Column(String(64), nullable=False, comment='原版本ID')
    to_version_id = Column(String(64), nullable=False, comment='目标版本ID')
    reason = Column(Text, comment='回滚原因')

    # 触发信息
    trigger_type = Column(String(32), comment='触发类型（manual/auto）')
    trigger_condition = Column(JSON, comment='触发条件')

    # 时间信息
    rolled_back_at = Column(DateTime, default=datetime.now, comment='回滚时间')
    rolled_back_by = Column(String(64), comment='回滚人')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


@dataclass
class VersionPerformance:
    """版本性能"""
    version_id: str
    version_number: str
    usage_count: int
    success_rate: float
    avg_viral_score: float
    avg_engagement_rate: float


class VersionManager:
    """
    版本管理器

    功能：
    1. 版本创建与管理
    2. 版本激活与切换
    3. 版本性能追踪
    4. 自动回滚
    5. 版本对比
    """

    def __init__(
        self,
        db: Session,
        auto_rollback: bool = True,
        rollback_threshold: float = 0.8  # 性能下降阈值
    ):
        self.db = db
        self.auto_rollback = auto_rollback
        self.rollback_threshold = rollback_threshold

    def create_version(
        self,
        version_type: VersionType,
        version_name: str,
        version_number: str,
        content: Dict,
        created_by: Optional[str] = None
    ) -> Version:
        """
        创建版本

        Args:
            version_type: 版本类型
            version_name: 版本名称
            version_number: 版本号
            content: 版本内容
            created_by: 创建人

        Returns:
            版本对象
        """
        import uuid

        version_id = f"ver_{uuid.uuid4().hex[:16]}"

        # 计算内容哈希
        content_str = json.dumps(content, sort_keys=True)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()

        version = Version(
            version_id=version_id,
            version_type=version_type,
            version_name=version_name,
            version_number=version_number,
            content=content,
            content_hash=content_hash,
            status=VersionStatus.DRAFT,
            created_by=created_by
        )

        self.db.add(version)
        self.db.commit()

        logger.info(f"✅ 版本已创建: {version_id} ({version_name} {version_number})")

        return version

    def activate_version(self, version_id: str):
        """
        激活版本

        Args:
            version_id: 版本ID
        """
        version = self.db.query(Version).filter(
            Version.version_id == version_id
        ).first()

        if not version:
            raise ValueError(f"版本不存在: {version_id}")

        # 取消同类型的其他默认版本
        self.db.query(Version).filter(
            Version.version_type == version.version_type,
            Version.is_default == True
        ).update({'is_default': False})

        # 激活当前版本
        version.status = VersionStatus.ACTIVE
        version.is_default = True
        version.activated_at = datetime.now()

        self.db.commit()

        logger.info(f"✅ 版本已激活: {version_id}")

    def get_active_version(
        self,
        version_type: VersionType,
        version_name: Optional[str] = None
    ) -> Optional[Version]:
        """
        获取激活的版本

        Args:
            version_type: 版本类型
            version_name: 版本名称（可选）

        Returns:
            版本对象
        """
        query = self.db.query(Version).filter(
            Version.version_type == version_type,
            Version.is_default == True,
            Version.status == VersionStatus.ACTIVE
        )

        if version_name:
            query = query.filter(Version.version_name == version_name)

        return query.first()

    def record_usage(
        self,
        version_id: str,
        generation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        note_id: Optional[str] = None,
        success: Optional[bool] = None,
        result_metrics: Optional[Dict] = None
    ):
        """
        记录版本使用

        Args:
            version_id: 版本ID
            generation_id: 生成ID
            task_id: 任务ID
            note_id: 笔记ID
            success: 是否成功
            result_metrics: 结果指标
        """
        import uuid

        usage_id = f"usage_{uuid.uuid4().hex[:16]}"

        usage = VersionUsage(
            usage_id=usage_id,
            version_id=version_id,
            generation_id=generation_id,
            task_id=task_id,
            note_id=note_id,
            success=success,
            result_metrics=result_metrics
        )

        self.db.add(usage)

        # 更新版本使用次数
        version = self.db.query(Version).filter(
            Version.version_id == version_id
        ).first()

        if version:
            version.usage_count += 1

        self.db.commit()

    def get_version_performance(
        self,
        version_id: str,
        time_window_hours: int = 24
    ) -> VersionPerformance:
        """
        获取版本性能

        Args:
            version_id: 版本ID
            time_window_hours: 时间窗口（小时）

        Returns:
            版本性能
        """
        version = self.db.query(Version).filter(
            Version.version_id == version_id
        ).first()

        if not version:
            raise ValueError(f"版本不存在: {version_id}")

        # 获取时间窗口内的使用记录
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        usages = self.db.query(VersionUsage).filter(
            VersionUsage.version_id == version_id,
            VersionUsage.used_at >= cutoff_time
        ).all()

        if not usages:
            return VersionPerformance(
                version_id=version_id,
                version_number=version.version_number,
                usage_count=0,
                success_rate=0.0,
                avg_viral_score=0.0,
                avg_engagement_rate=0.0
            )

        # 计算性能指标
        success_count = sum(1 for u in usages if u.success)
        success_rate = success_count / len(usages)

        viral_scores = [
            u.result_metrics.get('viral_score', 0)
            for u in usages
            if u.result_metrics and 'viral_score' in u.result_metrics
        ]
        avg_viral_score = sum(viral_scores) / len(viral_scores) if viral_scores else 0.0

        engagement_rates = [
            u.result_metrics.get('engagement_rate', 0)
            for u in usages
            if u.result_metrics and 'engagement_rate' in u.result_metrics
        ]
        avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0

        return VersionPerformance(
            version_id=version_id,
            version_number=version.version_number,
            usage_count=len(usages),
            success_rate=success_rate,
            avg_viral_score=avg_viral_score,
            avg_engagement_rate=avg_engagement_rate
        )

    async def check_and_rollback(
        self,
        version_id: str,
        time_window_hours: int = 24
    ):
        """
        检查并自动回滚

        Args:
            version_id: 版本ID
            time_window_hours: 时间窗口（小时）
        """
        if not self.auto_rollback:
            return

        # 获取当前版本性能
        current_perf = self.get_version_performance(version_id, time_window_hours)

        # 获取历史版本性能（用于对比）
        version = self.db.query(Version).filter(
            Version.version_id == version_id
        ).first()

        if not version:
            return

        # 查找同类型的上一个激活版本
        previous_versions = self.db.query(Version).filter(
            Version.version_type == version.version_type,
            Version.version_id != version_id,
            Version.status == VersionStatus.DEPRECATED,
            Version.activated_at < version.activated_at
        ).order_by(Version.activated_at.desc()).limit(5).all()

        if not previous_versions:
            return

        # 对比性能
        for prev_version in previous_versions:
            prev_perf = self.get_version_performance(prev_version.version_id, time_window_hours * 7)

            # 如果当前版本性能显著下降
            if (current_perf.avg_viral_score < prev_perf.avg_viral_score * self.rollback_threshold or
                current_perf.success_rate < prev_perf.success_rate * self.rollback_threshold):

                # 触发回滚
                await self._rollback_to_version(
                    from_version_id=version_id,
                    to_version_id=prev_version.version_id,
                    reason=f"性能下降: viral_score {current_perf.avg_viral_score:.2f} < {prev_perf.avg_viral_score:.2f}, success_rate {current_perf.success_rate:.2f} < {prev_perf.success_rate:.2f}",
                    trigger_type='auto'
                )

                break

    async def _rollback_to_version(
        self,
        from_version_id: str,
        to_version_id: str,
        reason: str,
        trigger_type: str = 'manual',
        rolled_back_by: Optional[str] = None
    ):
        """
        回滚到指定版本

        Args:
            from_version_id: 原版本ID
            to_version_id: 目标版本ID
            reason: 回滚原因
            trigger_type: 触发类型
            rolled_back_by: 回滚人
        """
        import uuid

        # 记录回滚
        rollback_id = f"rollback_{uuid.uuid4().hex[:16]}"

        rollback = VersionRollback(
            rollback_id=rollback_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            reason=reason,
            trigger_type=trigger_type,
            rolled_back_by=rolled_back_by
        )

        self.db.add(rollback)

        # 弃用当前版本
        from_version = self.db.query(Version).filter(
            Version.version_id == from_version_id
        ).first()

        if from_version:
            from_version.status = VersionStatus.DEPRECATED
            from_version.is_default = False
            from_version.deprecated_at = datetime.now()

        # 激活目标版本
        to_version = self.db.query(Version).filter(
            Version.version_id == to_version_id
        ).first()

        if to_version:
            to_version.status = VersionStatus.ACTIVE
            to_version.is_default = True
            to_version.activated_at = datetime.now()

        self.db.commit()

        logger.warning(f"⚠️ 版本已回滚: {from_version_id} → {to_version_id}, 原因: {reason}")

    def compare_versions(
        self,
        version_id_1: str,
        version_id_2: str,
        time_window_hours: int = 24
    ) -> Dict:
        """
        对比两个版本

        Args:
            version_id_1: 版本1 ID
            version_id_2: 版本2 ID
            time_window_hours: 时间窗口（小时）

        Returns:
            对比结果
        """
        perf_1 = self.get_version_performance(version_id_1, time_window_hours)
        perf_2 = self.get_version_performance(version_id_2, time_window_hours)

        return {
            'version_1': {
                'version_id': perf_1.version_id,
                'version_number': perf_1.version_number,
                'usage_count': perf_1.usage_count,
                'success_rate': perf_1.success_rate,
                'avg_viral_score': perf_1.avg_viral_score,
                'avg_engagement_rate': perf_1.avg_engagement_rate
            },
            'version_2': {
                'version_id': perf_2.version_id,
                'version_number': perf_2.version_number,
                'usage_count': perf_2.usage_count,
                'success_rate': perf_2.success_rate,
                'avg_viral_score': perf_2.avg_viral_score,
                'avg_engagement_rate': perf_2.avg_engagement_rate
            },
            'comparison': {
                'viral_score_diff': perf_2.avg_viral_score - perf_1.avg_viral_score,
                'viral_score_lift': (perf_2.avg_viral_score / perf_1.avg_viral_score - 1) if perf_1.avg_viral_score > 0 else 0,
                'success_rate_diff': perf_2.success_rate - perf_1.success_rate,
                'engagement_rate_diff': perf_2.avg_engagement_rate - perf_1.avg_engagement_rate
            }
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建版本管理器
    manager = VersionManager(db, auto_rollback=True)

    # 2. 创建 Prompt 版本
    prompt_v1 = manager.create_version(
        version_type=VersionType.PROMPT,
        version_name='hook_generator',
        version_number='v1.0.0',
        content={
            'system_prompt': '你是一个爆款标题生成器...',
            'user_prompt_template': '请为以下话题生成标题: {topic}',
            'temperature': 0.8,
            'max_tokens': 100
        },
        created_by='admin'
    )

    # 3. 激活版本
    manager.activate_version(prompt_v1.version_id)

    # 4. 使用版本
    active_prompt = manager.get_active_version(VersionType.PROMPT, 'hook_generator')
    print(f"当前激活版本: {active_prompt.version_number}")

    # 5. 记录使用
    manager.record_usage(
        version_id=active_prompt.version_id,
        generation_id='gen_123',
        success=True,
        result_metrics={'viral_score': 0.85, 'engagement_rate': 0.12}
    )

    # 6. 获取性能
    perf = manager.get_version_performance(active_prompt.version_id)
    print(f"版本性能: viral_score={perf.avg_viral_score:.2f}")

    # 7. 检查并自动回滚
    await manager.check_and_rollback(active_prompt.version_id)

    # 8. 对比版本
    comparison = manager.compare_versions(prompt_v1.version_id, prompt_v2.version_id)
    print(f"版本对比: {comparison}")
