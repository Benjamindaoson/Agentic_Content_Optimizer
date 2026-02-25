"""
趋势检测模块

用于检测模式的时效性，避免过拟合
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from scipy import stats
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from app.db import Pattern, PatternSample, Generation, OnlineMetrics

logger = logging.getLogger(__name__)


@dataclass
class TrendAnalysis:
    """趋势分析结果"""
    pattern_id: str
    trend_type: str  # 'rising', 'stable', 'declining', 'dead'
    trend_score: float  # -1.0 到 1.0
    confidence: float  # 0.0 到 1.0
    recent_success_rate: float
    historical_success_rate: float
    sample_count: int
    recommendation: str  # 'keep', 'refresh', 'remove'


class TrendDetector:
    """
    趋势检测器

    功能：
    1. 检测模式的时效性
    2. 识别上升/下降趋势
    3. 标记过时模式
    4. 推荐刷新策略
    """

    def __init__(
        self,
        lookback_days: int = 30,
        recent_days: int = 7,
        min_samples: int = 10,
        decline_threshold: float = 0.2,
        dead_threshold: float = 0.1
    ):
        """
        Args:
            lookback_days: 回溯天数
            recent_days: 近期天数（用于对比）
            min_samples: 最小样本数
            decline_threshold: 下降阈值
            dead_threshold: 死亡阈值
        """
        self.lookback_days = lookback_days
        self.recent_days = recent_days
        self.min_samples = min_samples
        self.decline_threshold = decline_threshold
        self.dead_threshold = dead_threshold

    async def analyze_pattern_trend(
        self,
        pattern_id: str,
        db: Session
    ) -> TrendAnalysis:
        """
        分析单个模式的趋势

        Args:
            pattern_id: 模式ID
            db: 数据库会话

        Returns:
            趋势分析结果
        """
        # 1. 获取模式
        pattern = db.query(Pattern).filter(Pattern.pattern_id == pattern_id).first()
        if not pattern:
            raise ValueError(f"模式不存在: {pattern_id}")

        # 2. 获取历史数据
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        recent_cutoff = datetime.now() - timedelta(days=self.recent_days)

        # 获取使用该模式生成的内容
        generations = db.query(Generation).filter(
            and_(
                Generation.pattern_id == pattern_id,
                Generation.created_at >= cutoff_date
            )
        ).all()

        if len(generations) < self.min_samples:
            return TrendAnalysis(
                pattern_id=pattern_id,
                trend_type='insufficient_data',
                trend_score=0.0,
                confidence=0.0,
                recent_success_rate=0.0,
                historical_success_rate=pattern.success_rate,
                sample_count=len(generations),
                recommendation='wait'
            )

        # 3. 计算历史和近期成功率
        historical_metrics = []
        recent_metrics = []

        for gen in generations:
            # 获取线上指标
            metrics = db.query(OnlineMetrics).filter(
                OnlineMetrics.generation_id == gen.generation_id
            ).first()

            if metrics and metrics.viral_score is not None:
                is_success = metrics.viral_score >= 0.7  # 成功阈值

                if gen.created_at >= recent_cutoff:
                    recent_metrics.append(is_success)
                historical_metrics.append(is_success)

        if not historical_metrics:
            return TrendAnalysis(
                pattern_id=pattern_id,
                trend_type='no_metrics',
                trend_score=0.0,
                confidence=0.0,
                recent_success_rate=0.0,
                historical_success_rate=pattern.success_rate,
                sample_count=len(generations),
                recommendation='wait'
            )

        historical_success_rate = np.mean(historical_metrics)
        recent_success_rate = np.mean(recent_metrics) if recent_metrics else historical_success_rate

        # 4. 计算趋势
        trend_score = recent_success_rate - historical_success_rate
        confidence = min(len(recent_metrics) / self.min_samples, 1.0)

        # 5. 判断趋势类型
        if recent_success_rate < self.dead_threshold:
            trend_type = 'dead'
            recommendation = 'remove'
        elif trend_score < -self.decline_threshold:
            trend_type = 'declining'
            recommendation = 'refresh'
        elif trend_score > self.decline_threshold:
            trend_type = 'rising'
            recommendation = 'keep'
        else:
            trend_type = 'stable'
            recommendation = 'keep'

        return TrendAnalysis(
            pattern_id=pattern_id,
            trend_type=trend_type,
            trend_score=trend_score,
            confidence=confidence,
            recent_success_rate=recent_success_rate,
            historical_success_rate=historical_success_rate,
            sample_count=len(generations),
            recommendation=recommendation
        )

    async def analyze_all_patterns(
        self,
        db: Session,
        category: Optional[str] = None
    ) -> List[TrendAnalysis]:
        """
        分析所有模式的趋势

        Args:
            db: 数据库会话
            category: 分类过滤

        Returns:
            趋势分析结果列表
        """
        # 获取所有模式
        query = db.query(Pattern)
        if category:
            query = query.filter(Pattern.category == category)

        patterns = query.all()

        results = []
        for pattern in patterns:
            try:
                analysis = await self.analyze_pattern_trend(pattern.pattern_id, db)
                results.append(analysis)
            except Exception as e:
                logger.error(f"分析模式趋势失败: {pattern.pattern_id}, error={e}")
                continue

        return results

    async def detect_seasonal_patterns(
        self,
        db: Session,
        category: str
    ) -> Dict[str, List[str]]:
        """
        检测季节性模式

        Args:
            db: 数据库会话
            category: 分类

        Returns:
            季节性模式字典 {'spring': [...], 'summer': [...], ...}
        """
        # 获取过去一年的数据
        cutoff_date = datetime.now() - timedelta(days=365)

        patterns = db.query(Pattern).filter(
            and_(
                Pattern.category == category,
                Pattern.created_at >= cutoff_date
            )
        ).all()

        seasonal_patterns = {
            'spring': [],  # 3-5月
            'summer': [],  # 6-8月
            'autumn': [],  # 9-11月
            'winter': []   # 12-2月
        }

        for pattern in patterns:
            # 获取该模式的样本
            samples = db.query(PatternSample).filter(
                PatternSample.pattern_id == pattern.pattern_id
            ).all()

            # 统计各季节的样本数
            season_counts = defaultdict(int)
            for sample in samples:
                if sample.publish_time:
                    month = sample.publish_time.month
                    if 3 <= month <= 5:
                        season_counts['spring'] += 1
                    elif 6 <= month <= 8:
                        season_counts['summer'] += 1
                    elif 9 <= month <= 11:
                        season_counts['autumn'] += 1
                    else:
                        season_counts['winter'] += 1

            # 找出主要季节
            if season_counts:
                main_season = max(season_counts, key=season_counts.get)
                if season_counts[main_season] / sum(season_counts.values()) > 0.6:
                    seasonal_patterns[main_season].append(pattern.pattern_id)

        return seasonal_patterns

    async def calculate_pattern_freshness(
        self,
        pattern_id: str,
        db: Session
    ) -> float:
        """
        计算模式新鲜度

        Args:
            pattern_id: 模式ID
            db: 数据库会话

        Returns:
            新鲜度分数 (0.0 到 1.0)
        """
        pattern = db.query(Pattern).filter(Pattern.pattern_id == pattern_id).first()
        if not pattern:
            return 0.0

        # 1. 时间衰减
        days_since_created = (datetime.now() - pattern.created_at).days
        time_decay = np.exp(-days_since_created / 30)  # 30天半衰期

        # 2. 使用频率
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_usage = db.query(func.count(Generation.generation_id)).filter(
            and_(
                Generation.pattern_id == pattern_id,
                Generation.created_at >= recent_cutoff
            )
        ).scalar()

        usage_score = min(recent_usage / 10, 1.0)  # 归一化

        # 3. 成功率
        success_score = pattern.success_rate

        # 综合评分
        freshness = 0.3 * time_decay + 0.3 * usage_score + 0.4 * success_score

        return freshness

    async def get_stale_patterns(
        self,
        db: Session,
        freshness_threshold: float = 0.3
    ) -> List[str]:
        """
        获取陈旧模式

        Args:
            db: 数据库会话
            freshness_threshold: 新鲜度阈值

        Returns:
            陈旧模式ID列表
        """
        patterns = db.query(Pattern).all()

        stale_patterns = []
        for pattern in patterns:
            freshness = await self.calculate_pattern_freshness(pattern.pattern_id, db)
            if freshness < freshness_threshold:
                stale_patterns.append(pattern.pattern_id)

        return stale_patterns

    async def recommend_refresh_strategy(
        self,
        trend_analysis: TrendAnalysis
    ) -> Dict[str, any]:
        """
        推荐刷新策略

        Args:
            trend_analysis: 趋势分析结果

        Returns:
            刷新策略
        """
        if trend_analysis.recommendation == 'remove':
            return {
                'action': 'remove',
                'reason': '模式已死亡，成功率过低',
                'priority': 'high'
            }

        elif trend_analysis.recommendation == 'refresh':
            return {
                'action': 'resample',
                'reason': '模式呈下降趋势，需要重新采样',
                'priority': 'medium',
                'suggested_samples': 20
            }

        elif trend_analysis.trend_type == 'rising':
            return {
                'action': 'expand',
                'reason': '模式呈上升趋势，可以扩展样本',
                'priority': 'low',
                'suggested_samples': 10
            }

        else:
            return {
                'action': 'keep',
                'reason': '模式稳定，保持现状',
                'priority': 'low'
            }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())
    detector = TrendDetector(
        lookback_days=30,
        recent_days=7,
        min_samples=10
    )

    # 1. 分析单个模式
    analysis = await detector.analyze_pattern_trend('pattern_123', db)
    print(f"趋势类型: {analysis.trend_type}")
    print(f"趋势分数: {analysis.trend_score:.2f}")
    print(f"推荐: {analysis.recommendation}")

    # 2. 分析所有模式
    all_analyses = await detector.analyze_all_patterns(db, category='美妆')
    declining = [a for a in all_analyses if a.trend_type == 'declining']
    print(f"下降趋势模式: {len(declining)} 个")

    # 3. 检测季节性模式
    seasonal = await detector.detect_seasonal_patterns(db, '美妆')
    print(f"春季模式: {len(seasonal['spring'])} 个")

    # 4. 获取陈旧模式
    stale = await detector.get_stale_patterns(db, freshness_threshold=0.3)
    print(f"陈旧模式: {len(stale)} 个")

    # 5. 推荐刷新策略
    strategy = await detector.recommend_refresh_strategy(analysis)
    print(f"刷新策略: {strategy}")
