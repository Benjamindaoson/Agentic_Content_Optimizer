"""
特征库 (Feature Store)

用于标准化特征管理，支持离线/在线同口径、特征漂移监控
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import Session
from app.core.database import Base

logger = logging.getLogger(__name__)


class FeatureType(str, Enum):
    """特征类型"""
    NUMERICAL = 'numerical'  # 数值型
    CATEGORICAL = 'categorical'  # 分类型
    BOOLEAN = 'boolean'  # 布尔型
    TEXT = 'text'  # 文本型


# ==================== 数据库模型 ====================

class FeatureDefinition(Base):
    """特征定义表"""
    __tablename__ = 'feature_definitions'

    feature_id = Column(String(64), primary_key=True, comment='特征ID')
    feature_name = Column(String(128), nullable=False, unique=True, comment='特征名称')
    feature_type = Column(String(32), nullable=False, comment='特征类型')

    # 特征描述
    description = Column(Text, comment='特征描述')
    category = Column(String(64), comment='特征分类（text/structure/timing/metrics/author）')

    # 计算逻辑
    computation_logic = Column(Text, comment='计算逻辑（Python 代码或 SQL）')
    dependencies = Column(JSON, comment='依赖的其他特征')

    # 统计信息
    min_value = Column(Float, comment='最小值')
    max_value = Column(Float, comment='最大值')
    mean_value = Column(Float, comment='平均值')
    std_value = Column(Float, comment='标准差')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    is_active = Column(Boolean, default=True, comment='是否激活')
    metadata = Column(JSON, comment='其他元数据')


class FeatureNote(Base):
    """笔记特征表"""
    __tablename__ = 'features_note'

    feature_note_id = Column(String(64), primary_key=True, comment='特征记录ID')
    note_id = Column(String(64), ForeignKey('xhs_notes.note_id'), nullable=False, comment='笔记ID')

    # 特征值（JSON 存储所有特征）
    features = Column(JSON, nullable=False, comment='特征值字典')

    # 版本信息
    feature_version = Column(String(32), comment='特征版本')
    computed_at = Column(DateTime, default=datetime.now, comment='计算时间')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


class FeaturePattern(Base):
    """模式特征表"""
    __tablename__ = 'features_pattern'

    feature_pattern_id = Column(String(64), primary_key=True, comment='特征记录ID')
    pattern_id = Column(String(64), ForeignKey('patterns.pattern_id'), nullable=False, comment='模式ID')

    # 特征值
    features = Column(JSON, nullable=False, comment='特征值字典')

    # 版本信息
    feature_version = Column(String(32), comment='特征版本')
    computed_at = Column(DateTime, default=datetime.now, comment='计算时间')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


class FeatureDrift(Base):
    """特征漂移监控表"""
    __tablename__ = 'feature_drift'

    drift_id = Column(String(64), primary_key=True, comment='漂移ID')
    feature_name = Column(String(128), nullable=False, comment='特征名称')

    # 漂移信息
    baseline_mean = Column(Float, comment='基线均值')
    baseline_std = Column(Float, comment='基线标准差')
    current_mean = Column(Float, comment='当前均值')
    current_std = Column(Float, comment='当前标准差')

    # 漂移指标
    drift_score = Column(Float, comment='漂移分数')
    is_drifted = Column(Boolean, comment='是否漂移')

    # 时间信息
    baseline_start = Column(DateTime, comment='基线开始时间')
    baseline_end = Column(DateTime, comment='基线结束时间')
    current_start = Column(DateTime, comment='当前开始时间')
    current_end = Column(DateTime, comment='当前结束时间')
    detected_at = Column(DateTime, default=datetime.now, comment='检测时间')

    # 元数据
    metadata = Column(JSON, comment='其他元数据')


@dataclass
class FeatureStats:
    """特征统计"""
    feature_name: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    missing_rate: float


class FeatureStore:
    """
    特征库

    功能：
    1. 特征定义管理
    2. 特征计算与存储
    3. 离线/在线同口径
    4. 特征漂移监控
    5. 特征统计
    """

    def __init__(
        self,
        db: Session,
        feature_version: str = 'v1.0.0'
    ):
        self.db = db
        self.feature_version = feature_version

    def register_feature(
        self,
        feature_name: str,
        feature_type: FeatureType,
        description: str,
        category: str,
        computation_logic: Optional[str] = None,
        dependencies: Optional[List[str]] = None
    ) -> FeatureDefinition:
        """
        注册特征定义

        Args:
            feature_name: 特征名称
            feature_type: 特征类型
            description: 特征描述
            category: 特征分类
            computation_logic: 计算逻辑
            dependencies: 依赖特征

        Returns:
            特征定义
        """
        import uuid

        feature_id = f"feat_{uuid.uuid4().hex[:16]}"

        feature_def = FeatureDefinition(
            feature_id=feature_id,
            feature_name=feature_name,
            feature_type=feature_type.value,
            description=description,
            category=category,
            computation_logic=computation_logic,
            dependencies=dependencies or []
        )

        self.db.add(feature_def)
        self.db.commit()

        logger.info(f"✅ 特征已注册: {feature_name}")

        return feature_def

    def compute_and_store_note_features(
        self,
        note_id: str,
        features: Dict[str, Any]
    ):
        """
        计算并存储笔记特征

        Args:
            note_id: 笔记ID
            features: 特征字典
        """
        import uuid

        feature_note_id = f"fn_{uuid.uuid4().hex[:16]}"

        feature_note = FeatureNote(
            feature_note_id=feature_note_id,
            note_id=note_id,
            features=features,
            feature_version=self.feature_version
        )

        self.db.add(feature_note)
        self.db.commit()

        # 更新特征统计
        self._update_feature_stats(features)

    def compute_and_store_pattern_features(
        self,
        pattern_id: str,
        features: Dict[str, Any]
    ):
        """
        计算并存储模式特征

        Args:
            pattern_id: 模式ID
            features: 特征字典
        """
        import uuid

        feature_pattern_id = f"fp_{uuid.uuid4().hex[:16]}"

        feature_pattern = FeaturePattern(
            feature_pattern_id=feature_pattern_id,
            pattern_id=pattern_id,
            features=features,
            feature_version=self.feature_version
        )

        self.db.add(feature_pattern)
        self.db.commit()

    def get_note_features(
        self,
        note_id: str,
        feature_names: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        获取笔记特征

        Args:
            note_id: 笔记ID
            feature_names: 特征名称列表（None 则返回所有特征）

        Returns:
            特征字典
        """
        feature_note = self.db.query(FeatureNote).filter(
            FeatureNote.note_id == note_id
        ).order_by(FeatureNote.computed_at.desc()).first()

        if not feature_note:
            return None

        features = feature_note.features

        if feature_names:
            features = {k: v for k, v in features.items() if k in feature_names}

        return features

    def get_pattern_features(
        self,
        pattern_id: str,
        feature_names: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        获取模式特征

        Args:
            pattern_id: 模式ID
            feature_names: 特征名称列表

        Returns:
            特征字典
        """
        feature_pattern = self.db.query(FeaturePattern).filter(
            FeaturePattern.pattern_id == pattern_id
        ).order_by(FeaturePattern.computed_at.desc()).first()

        if not feature_pattern:
            return None

        features = feature_pattern.features

        if feature_names:
            features = {k: v for k, v in features.items() if k in feature_names}

        return features

    def get_batch_features(
        self,
        note_ids: List[str],
        feature_names: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        批量获取特征

        Args:
            note_ids: 笔记ID列表
            feature_names: 特征名称列表

        Returns:
            特征DataFrame
        """
        feature_notes = self.db.query(FeatureNote).filter(
            FeatureNote.note_id.in_(note_ids)
        ).all()

        data = []
        for fn in feature_notes:
            features = fn.features
            if feature_names:
                features = {k: v for k, v in features.items() if k in feature_names}

            row = {'note_id': fn.note_id, **features}
            data.append(row)

        return pd.DataFrame(data)

    def _update_feature_stats(self, features: Dict[str, Any]):
        """更新特征统计"""
        for feature_name, feature_value in features.items():
            feature_def = self.db.query(FeatureDefinition).filter(
                FeatureDefinition.feature_name == feature_name
            ).first()

            if not feature_def:
                continue

            # 只更新数值型特征的统计
            if feature_def.feature_type == FeatureType.NUMERICAL.value:
                try:
                    value = float(feature_value)

                    # 更新最小值/最大值
                    if feature_def.min_value is None or value < feature_def.min_value:
                        feature_def.min_value = value

                    if feature_def.max_value is None or value > feature_def.max_value:
                        feature_def.max_value = value

                    # 更新均值和标准差（增量更新）
                    # 这里简化处理，实际应该用更精确的增量算法

                except (ValueError, TypeError):
                    pass

        self.db.commit()

    async def detect_feature_drift(
        self,
        feature_name: str,
        baseline_days: int = 30,
        current_days: int = 7,
        drift_threshold: float = 0.1
    ) -> Optional[FeatureDrift]:
        """
        检测特征漂移

        Args:
            feature_name: 特征名称
            baseline_days: 基线天数
            current_days: 当前天数
            drift_threshold: 漂移阈值

        Returns:
            漂移记录
        """
        # 1. 获取基线数据
        baseline_end = datetime.now() - timedelta(days=current_days)
        baseline_start = baseline_end - timedelta(days=baseline_days)

        baseline_features = self.db.query(FeatureNote).filter(
            FeatureNote.computed_at >= baseline_start,
            FeatureNote.computed_at < baseline_end
        ).all()

        baseline_values = [
            fn.features.get(feature_name)
            for fn in baseline_features
            if fn.features.get(feature_name) is not None
        ]

        if not baseline_values:
            logger.warning(f"基线数据不足: {feature_name}")
            return None

        baseline_mean = np.mean(baseline_values)
        baseline_std = np.std(baseline_values)

        # 2. 获取当前数据
        current_start = datetime.now() - timedelta(days=current_days)
        current_end = datetime.now()

        current_features = self.db.query(FeatureNote).filter(
            FeatureNote.computed_at >= current_start,
            FeatureNote.computed_at < current_end
        ).all()

        current_values = [
            fn.features.get(feature_name)
            for fn in current_features
            if fn.features.get(feature_name) is not None
        ]

        if not current_values:
            logger.warning(f"当前数据不足: {feature_name}")
            return None

        current_mean = np.mean(current_values)
        current_std = np.std(current_values)

        # 3. 计算漂移分数（使用 PSI - Population Stability Index）
        # 简化版：使用均值差异
        drift_score = abs(current_mean - baseline_mean) / (baseline_std + 1e-6)

        is_drifted = drift_score > drift_threshold

        # 4. 记录漂移
        import uuid
        drift_id = f"drift_{uuid.uuid4().hex[:16]}"

        drift = FeatureDrift(
            drift_id=drift_id,
            feature_name=feature_name,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            current_mean=current_mean,
            current_std=current_std,
            drift_score=drift_score,
            is_drifted=is_drifted,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            current_start=current_start,
            current_end=current_end
        )

        self.db.add(drift)
        self.db.commit()

        if is_drifted:
            logger.warning(f"⚠️ 特征漂移: {feature_name}, drift_score={drift_score:.4f}")

        return drift

    async def monitor_all_features(
        self,
        baseline_days: int = 30,
        current_days: int = 7,
        drift_threshold: float = 0.1
    ) -> List[FeatureDrift]:
        """
        监控所有特征

        Args:
            baseline_days: 基线天数
            current_days: 当前天数
            drift_threshold: 漂移阈值

        Returns:
            漂移记录列表
        """
        # 获取所有数值型特征
        feature_defs = self.db.query(FeatureDefinition).filter(
            FeatureDefinition.feature_type == FeatureType.NUMERICAL.value,
            FeatureDefinition.is_active == True
        ).all()

        drifts = []

        for feature_def in feature_defs:
            try:
                drift = await self.detect_feature_drift(
                    feature_name=feature_def.feature_name,
                    baseline_days=baseline_days,
                    current_days=current_days,
                    drift_threshold=drift_threshold
                )

                if drift and drift.is_drifted:
                    drifts.append(drift)

            except Exception as e:
                logger.error(f"监控特征失败: {feature_def.feature_name}, error={e}")

        logger.info(f"✅ 特征监控完成: 发现 {len(drifts)} 个漂移特征")

        return drifts

    def get_feature_stats(self, feature_name: str) -> Optional[FeatureStats]:
        """获取特征统计"""
        feature_def = self.db.query(FeatureDefinition).filter(
            FeatureDefinition.feature_name == feature_name
        ).first()

        if not feature_def:
            return None

        # 获取所有特征值
        feature_notes = self.db.query(FeatureNote).all()

        values = [
            fn.features.get(feature_name)
            for fn in feature_notes
            if fn.features.get(feature_name) is not None
        ]

        if not values:
            return None

        count = len(values)
        missing_count = len(feature_notes) - count
        missing_rate = missing_count / len(feature_notes) if feature_notes else 0

        return FeatureStats(
            feature_name=feature_name,
            count=count,
            mean=np.mean(values),
            std=np.std(values),
            min=np.min(values),
            max=np.max(values),
            missing_rate=missing_rate
        )


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db
    from app.ml.feature_extractor import FeatureExtractor

    db = next(get_db())

    # 1. 创建特征库
    store = FeatureStore(db, feature_version='v1.0.0')

    # 2. 注册特征定义
    store.register_feature(
        feature_name='title_length',
        feature_type=FeatureType.NUMERICAL,
        description='标题长度',
        category='text',
        computation_logic='len(title)'
    )

    # 3. 计算并存储特征
    extractor = FeatureExtractor()
    features = extractor.extract_all_features(
        title='测试标题',
        text='测试内容',
        publish_time=datetime.now(),
        metrics={'views': 1000, 'likes': 100},
        author_id=None,
        db=None
    )

    store.compute_and_store_note_features('note_123', features)

    # 4. 获取特征
    note_features = store.get_note_features('note_123')
    print(f"笔记特征: {note_features}")

    # 5. 批量获取
    df = store.get_batch_features(['note_123', 'note_456'])
    print(f"批量特征: {df}")

    # 6. 检测漂移
    drift = await store.detect_feature_drift('title_length')
    if drift and drift.is_drifted:
        print(f"特征漂移: {drift.feature_name}, score={drift.drift_score:.4f}")

    # 7. 监控所有特征
    drifts = await store.monitor_all_features()
    print(f"漂移特征数: {len(drifts)}")

    # 8. 获取统计
    stats = store.get_feature_stats('title_length')
    print(f"特征统计: mean={stats.mean:.2f}, std={stats.std:.2f}")
