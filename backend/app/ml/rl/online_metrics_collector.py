"""
线上指标回收器

用于收集已发布内容的真实表现数据，形成 GRPO 闭环
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import asyncio

from app.db import Generation, OnlineMetrics, XHSNote, XHSMetrics
from app.data.crawlers import XHSCrawler


@dataclass
class MetricsSnapshot:
    """指标快照"""
    generation_id: str
    note_id: str
    platform: str

    # 时间信息
    published_at: datetime
    collected_at: datetime
    hours_since_publish: float

    # 指标数据
    views: int
    likes: int
    comments: int
    collects: int
    shares: int
    follows: int

    # 计算指标
    engagement_rate: float
    viral_score: float
    velocity_score: float

    # 预测对比
    predicted_viral_score: float
    actual_vs_predicted: float  # 实际 / 预测


class OnlineMetricsCollector:
    """
    线上指标回收器

    核心功能：
    1. 定期回收已发布内容的真实指标
    2. 计算实际表现 vs 预测表现
    3. 存储到 online_metrics 表
    4. 为 GRPO 训练提供数据
    """

    def __init__(self, crawler: Optional[XHSCrawler] = None):
        self.crawler = crawler or XHSCrawler()

    async def collect_metrics(
        self,
        generation_id: str,
        note_id: str,
        db: Session
    ) -> Optional[MetricsSnapshot]:
        """
        收集单个生成内容的线上指标

        Args:
            generation_id: 生成记录 ID
            note_id: 笔记 ID
            db: 数据库会话

        Returns:
            指标快照
        """
        # 1. 查询生成记录
        generation = db.query(Generation).filter_by(
            generation_id=generation_id
        ).first()

        if not generation:
            return None

        if not generation.published_at:
            return None

        # 2. 爬取最新指标
        try:
            note_data = await self.crawler.fetch_note_by_id(note_id)

            if not note_data:
                return None

            # 3. 计算时间差
            collected_at = datetime.now()
            hours_since_publish = (
                collected_at - generation.published_at
            ).total_seconds() / 3600

            # 4. 计算指标
            views = note_data.get('views', 0)
            likes = note_data.get('likes', 0)
            comments = note_data.get('comments', 0)
            collects = note_data.get('collects', 0)
            shares = note_data.get('shares', 0)
            follows = note_data.get('follows', 0)

            engagement_rate = (
                (likes + comments + collects + shares) / max(views, 1)
            )

            # 爆款分数（简化版）
            viral_score = min(
                (views / 10000) * 0.4 +
                (likes / 1000) * 0.3 +
                (collects / 500) * 0.2 +
                (comments / 200) * 0.1,
                1.0
            )

            # 速度分数（24小时内的增长速度）
            if hours_since_publish > 0:
                velocity_score = min(
                    (views / hours_since_publish) / 1000,
                    1.0
                )
            else:
                velocity_score = 0.0

            # 5. 对比预测
            predicted_viral_score = generation.predicted_viral_score or 0.5
            actual_vs_predicted = viral_score / max(predicted_viral_score, 0.01)

            # 6. 创建快照
            snapshot = MetricsSnapshot(
                generation_id=generation_id,
                note_id=note_id,
                platform=generation.platform,
                published_at=generation.published_at,
                collected_at=collected_at,
                hours_since_publish=hours_since_publish,
                views=views,
                likes=likes,
                comments=comments,
                collects=collects,
                shares=shares,
                follows=follows,
                engagement_rate=engagement_rate,
                viral_score=viral_score,
                velocity_score=velocity_score,
                predicted_viral_score=predicted_viral_score,
                actual_vs_predicted=actual_vs_predicted
            )

            # 7. 保存到数据库
            await self._save_snapshot(snapshot, db)

            return snapshot

        except Exception as e:
            print(f"收集指标失败: {e}")
            return None

    async def collect_batch_metrics(
        self,
        generation_ids: List[str],
        db: Session,
        max_concurrent: int = 5
    ) -> List[MetricsSnapshot]:
        """
        批量收集指标

        Args:
            generation_ids: 生成记录 ID 列表
            db: 数据库会话
            max_concurrent: 最大并发数

        Returns:
            指标快照列表
        """
        snapshots = []

        # 查询生成记录
        generations = db.query(Generation).filter(
            Generation.generation_id.in_(generation_ids),
            Generation.status == 'published',
            Generation.published_url.isnot(None)
        ).all()

        # 并发收集
        semaphore = asyncio.Semaphore(max_concurrent)

        async def collect_with_semaphore(gen):
            async with semaphore:
                # 从 URL 提取 note_id
                note_id = self._extract_note_id_from_url(gen.published_url)
                if note_id:
                    return await self.collect_metrics(
                        gen.generation_id,
                        note_id,
                        db
                    )
                return None

        tasks = [collect_with_semaphore(gen) for gen in generations]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, MetricsSnapshot):
                snapshots.append(result)

        return snapshots

    async def collect_recent_published(
        self,
        days: int = 7,
        db: Session = None
    ) -> List[MetricsSnapshot]:
        """
        收集最近发布内容的指标

        Args:
            days: 最近 N 天
            db: 数据库会话

        Returns:
            指标快照列表
        """
        if not db:
            return []

        # 查询最近发布的内容
        cutoff_date = datetime.now() - timedelta(days=days)

        generations = db.query(Generation).filter(
            Generation.status == 'published',
            Generation.published_at >= cutoff_date,
            Generation.published_url.isnot(None)
        ).all()

        generation_ids = [g.generation_id for g in generations]

        return await self.collect_batch_metrics(generation_ids, db)

    async def _save_snapshot(
        self,
        snapshot: MetricsSnapshot,
        db: Session
    ):
        """保存指标快照到数据库"""
        # 检查是否已存在
        existing = db.query(OnlineMetrics).filter_by(
            generation_id=snapshot.generation_id,
            collected_at=snapshot.collected_at
        ).first()

        if existing:
            # 更新
            existing.views = snapshot.views
            existing.likes = snapshot.likes
            existing.comments = snapshot.comments
            existing.collects = snapshot.collects
            existing.shares = snapshot.shares
            existing.follows = snapshot.follows
            existing.engagement_rate = snapshot.engagement_rate
            existing.viral_score = snapshot.viral_score
            existing.velocity_score = snapshot.velocity_score
            existing.actual_vs_predicted = snapshot.actual_vs_predicted
        else:
            # 新增
            metric = OnlineMetrics(
                generation_id=snapshot.generation_id,
                note_id=snapshot.note_id,
                platform=snapshot.platform,
                collected_at=snapshot.collected_at,
                hours_since_publish=snapshot.hours_since_publish,
                views=snapshot.views,
                likes=snapshot.likes,
                comments=snapshot.comments,
                collects=snapshot.collects,
                shares=snapshot.shares,
                follows=snapshot.follows,
                engagement_rate=snapshot.engagement_rate,
                viral_score=snapshot.viral_score,
                velocity_score=snapshot.velocity_score,
                predicted_viral_score=snapshot.predicted_viral_score,
                actual_vs_predicted=snapshot.actual_vs_predicted
            )
            db.add(metric)

        db.commit()

    def _extract_note_id_from_url(self, url: str) -> Optional[str]:
        """从 URL 提取 note_id"""
        if not url:
            return None

        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        if path:
            return path.split('/')[-1]
        return None

    async def get_performance_summary(
        self,
        generation_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        获取生成内容的表现摘要

        Args:
            generation_id: 生成记录 ID
            db: 数据库会话

        Returns:
            表现摘要
        """
        # 查询所有指标快照
        metrics = db.query(OnlineMetrics).filter_by(
            generation_id=generation_id
        ).order_by(OnlineMetrics.collected_at.asc()).all()

        if not metrics:
            return {
                'generation_id': generation_id,
                'status': 'no_data',
                'snapshots': []
            }

        # 最新快照
        latest = metrics[-1]

        # 增长趋势
        if len(metrics) > 1:
            first = metrics[0]
            views_growth = latest.views - first.views
            likes_growth = latest.likes - first.likes
            growth_rate = views_growth / max(first.views, 1)
        else:
            views_growth = 0
            likes_growth = 0
            growth_rate = 0.0

        return {
            'generation_id': generation_id,
            'status': 'active',
            'latest_snapshot': {
                'collected_at': latest.collected_at.isoformat(),
                'hours_since_publish': latest.hours_since_publish,
                'views': latest.views,
                'likes': latest.likes,
                'comments': latest.comments,
                'collects': latest.collects,
                'engagement_rate': latest.engagement_rate,
                'viral_score': latest.viral_score,
                'velocity_score': latest.velocity_score
            },
            'prediction_accuracy': {
                'predicted_viral_score': latest.predicted_viral_score,
                'actual_viral_score': latest.viral_score,
                'actual_vs_predicted': latest.actual_vs_predicted,
                'accuracy': 1.0 - abs(latest.viral_score - latest.predicted_viral_score)
            },
            'growth': {
                'views_growth': views_growth,
                'likes_growth': likes_growth,
                'growth_rate': growth_rate
            },
            'snapshots_count': len(metrics)
        }

    async def get_pattern_performance(
        self,
        pattern_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        获取模式的整体表现

        Args:
            pattern_id: 模式 ID
            db: 数据库会话

        Returns:
            模式表现摘要
        """
        # 查询使用该模式的所有生成记录
        generations = db.query(Generation).filter_by(
            pattern_id=pattern_id,
            status='published'
        ).all()

        if not generations:
            return {
                'pattern_id': pattern_id,
                'status': 'no_data',
                'total_generations': 0
            }

        generation_ids = [g.generation_id for g in generations]

        # 查询最新指标
        latest_metrics = []
        for gen_id in generation_ids:
            metric = db.query(OnlineMetrics).filter_by(
                generation_id=gen_id
            ).order_by(OnlineMetrics.collected_at.desc()).first()

            if metric:
                latest_metrics.append(metric)

        if not latest_metrics:
            return {
                'pattern_id': pattern_id,
                'status': 'no_metrics',
                'total_generations': len(generations)
            }

        # 计算平均表现
        avg_viral_score = sum(m.viral_score for m in latest_metrics) / len(latest_metrics)
        avg_engagement_rate = sum(m.engagement_rate for m in latest_metrics) / len(latest_metrics)
        avg_views = sum(m.views for m in latest_metrics) / len(latest_metrics)
        avg_accuracy = sum(
            1.0 - abs(m.viral_score - m.predicted_viral_score)
            for m in latest_metrics
        ) / len(latest_metrics)

        # 成功率（viral_score > 0.7）
        success_count = sum(1 for m in latest_metrics if m.viral_score > 0.7)
        success_rate = success_count / len(latest_metrics)

        return {
            'pattern_id': pattern_id,
            'status': 'active',
            'total_generations': len(generations),
            'metrics_count': len(latest_metrics),
            'performance': {
                'avg_viral_score': avg_viral_score,
                'avg_engagement_rate': avg_engagement_rate,
                'avg_views': avg_views,
                'success_rate': success_rate,
                'prediction_accuracy': avg_accuracy
            }
        }
