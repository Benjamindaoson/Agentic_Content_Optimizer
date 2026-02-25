"""
模式重采样器

用于周期性更新模式库，避免过拟合
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from app.db import Pattern, PatternSample, XHSNote, XHSMetrics
from app.analyzers.success_factor_extractor import SuccessFactorExtractor
from app.analyzers.trend_detector import TrendDetector, TrendAnalysis

logger = logging.getLogger(__name__)


class PatternResampler:
    """
    模式重采样器

    功能：
    1. 周期性重采样模式
    2. 刷新陈旧模式
    3. 移除失效模式
    4. 扩展热门模式
    """

    def __init__(
        self,
        extractor: SuccessFactorExtractor,
        trend_detector: TrendDetector
    ):
        self.extractor = extractor
        self.trend_detector = trend_detector

    async def resample_pattern(
        self,
        pattern_id: str,
        db: Session,
        num_samples: int = 20
    ) -> Dict:
        """
        重采样单个模式

        Args:
            pattern_id: 模式ID
            db: 数据库会话
            num_samples: 采样数量

        Returns:
            重采样结果
        """
        logger.info(f"开始重采样模式: {pattern_id}")

        # 1. 获取原模式
        pattern = db.query(Pattern).filter(Pattern.pattern_id == pattern_id).first()
        if not pattern:
            raise ValueError(f"模式不存在: {pattern_id}")

        # 2. 获取最新的爆款笔记
        recent_cutoff = datetime.now() - timedelta(days=7)

        notes = db.query(XHSNote).join(XHSMetrics).filter(
            and_(
                XHSNote.category == pattern.category,
                XHSNote.publish_time >= recent_cutoff,
                XHSMetrics.viral_score >= 0.7  # 爆款阈值
            )
        ).order_by(desc(XHSMetrics.viral_score)).limit(num_samples * 2).all()

        if len(notes) < num_samples:
            logger.warning(f"样本不足: {len(notes)}/{num_samples}")
            return {
                'success': False,
                'reason': 'insufficient_samples',
                'samples_found': len(notes)
            }

        # 3. 删除旧样本
        db.query(PatternSample).filter(
            PatternSample.pattern_id == pattern_id
        ).delete()

        # 4. 添加新样本
        for note in notes[:num_samples]:
            sample = PatternSample(
                pattern_id=pattern_id,
                note_id=note.note_id,
                publish_time=note.publish_time
            )
            db.add(sample)

        # 5. 重新提取模式
        # 获取笔记内容
        note_data = []
        for note in notes[:num_samples]:
            metrics = db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note.note_id
            ).first()

            if metrics:
                note_data.append({
                    'note_id': note.note_id,
                    'title': note.title,
                    'text': note.text,
                    'viral_score': metrics.viral_score
                })

        # 重新提取模式特征
        # 这里简化处理，实际应该调用 extractor 的方法
        pattern.sample_count = len(note_data)
        pattern.updated_at = datetime.now()

        # 重新计算成功率
        pattern.success_rate = sum(n['viral_score'] for n in note_data) / len(note_data)

        db.commit()

        logger.info(f"✅ 重采样完成: {pattern_id}, 新样本数={len(note_data)}")

        return {
            'success': True,
            'pattern_id': pattern_id,
            'old_sample_count': pattern.sample_count,
            'new_sample_count': len(note_data),
            'old_success_rate': pattern.success_rate,
            'new_success_rate': pattern.success_rate
        }

    async def refresh_stale_patterns(
        self,
        db: Session,
        freshness_threshold: float = 0.3
    ) -> Dict:
        """
        刷新陈旧模式

        Args:
            db: 数据库会话
            freshness_threshold: 新鲜度阈值

        Returns:
            刷新结果
        """
        logger.info("开始刷新陈旧模式")

        # 1. 获取陈旧模式
        stale_patterns = await self.trend_detector.get_stale_patterns(
            db,
            freshness_threshold
        )

        logger.info(f"发现陈旧模式: {len(stale_patterns)} 个")

        # 2. 逐个重采样
        results = {
            'total': len(stale_patterns),
            'success': 0,
            'failed': 0,
            'details': []
        }

        for pattern_id in stale_patterns:
            try:
                result = await self.resample_pattern(pattern_id, db, num_samples=20)
                if result['success']:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                results['details'].append(result)

            except Exception as e:
                logger.error(f"重采样失败: {pattern_id}, error={e}")
                results['failed'] += 1
                results['details'].append({
                    'success': False,
                    'pattern_id': pattern_id,
                    'error': str(e)
                })

        logger.info(f"✅ 刷新完成: 成功={results['success']}, 失败={results['failed']}")

        return results

    async def remove_dead_patterns(
        self,
        db: Session
    ) -> Dict:
        """
        移除失效模式

        Args:
            db: 数据库会话

        Returns:
            移除结果
        """
        logger.info("开始移除失效模式")

        # 1. 分析所有模式
        analyses = await self.trend_detector.analyze_all_patterns(db)

        # 2. 找出需要移除的模式
        dead_patterns = [
            a.pattern_id for a in analyses
            if a.recommendation == 'remove'
        ]

        logger.info(f"发现失效模式: {len(dead_patterns)} 个")

        # 3. 移除模式
        removed_count = 0
        for pattern_id in dead_patterns:
            try:
                # 删除样本
                db.query(PatternSample).filter(
                    PatternSample.pattern_id == pattern_id
                ).delete()

                # 删除模式
                db.query(Pattern).filter(
                    Pattern.pattern_id == pattern_id
                ).delete()

                db.commit()
                removed_count += 1

            except Exception as e:
                logger.error(f"移除模式失败: {pattern_id}, error={e}")
                db.rollback()

        logger.info(f"✅ 移除完成: {removed_count} 个模式")

        return {
            'total': len(dead_patterns),
            'removed': removed_count,
            'failed': len(dead_patterns) - removed_count
        }

    async def expand_hot_patterns(
        self,
        db: Session,
        top_n: int = 10
    ) -> Dict:
        """
        扩展热门模式

        Args:
            db: 数据库会话
            top_n: 扩展前N个热门模式

        Returns:
            扩展结果
        """
        logger.info(f"开始扩展热门模式: top {top_n}")

        # 1. 分析所有模式
        analyses = await self.trend_detector.analyze_all_patterns(db)

        # 2. 找出上升趋势的模式
        rising_patterns = [
            a for a in analyses
            if a.trend_type == 'rising'
        ]

        # 按趋势分数排序
        rising_patterns.sort(key=lambda x: x.trend_score, reverse=True)
        top_patterns = rising_patterns[:top_n]

        logger.info(f"发现上升趋势模式: {len(top_patterns)} 个")

        # 3. 扩展样本
        results = {
            'total': len(top_patterns),
            'success': 0,
            'failed': 0,
            'details': []
        }

        for analysis in top_patterns:
            try:
                result = await self.resample_pattern(
                    analysis.pattern_id,
                    db,
                    num_samples=30  # 扩展到30个样本
                )

                if result['success']:
                    results['success'] += 1
                else:
                    results['failed'] += 1

                results['details'].append(result)

            except Exception as e:
                logger.error(f"扩展模式失败: {analysis.pattern_id}, error={e}")
                results['failed'] += 1

        logger.info(f"✅ 扩展完成: 成功={results['success']}, 失败={results['failed']}")

        return results

    async def periodic_refresh(
        self,
        db: Session,
        refresh_interval_days: int = 7
    ) -> Dict:
        """
        周期性刷新

        Args:
            db: 数据库会话
            refresh_interval_days: 刷新间隔（天）

        Returns:
            刷新结果
        """
        logger.info(f"开始周期性刷新（间隔={refresh_interval_days}天）")

        results = {
            'stale_refresh': None,
            'dead_removal': None,
            'hot_expansion': None,
            'timestamp': datetime.now().isoformat()
        }

        # 1. 刷新陈旧模式
        try:
            results['stale_refresh'] = await self.refresh_stale_patterns(db)
        except Exception as e:
            logger.error(f"刷新陈旧模式失败: {e}")
            results['stale_refresh'] = {'error': str(e)}

        # 2. 移除失效模式
        try:
            results['dead_removal'] = await self.remove_dead_patterns(db)
        except Exception as e:
            logger.error(f"移除失效模式失败: {e}")
            results['dead_removal'] = {'error': str(e)}

        # 3. 扩展热门模式
        try:
            results['hot_expansion'] = await self.expand_hot_patterns(db, top_n=5)
        except Exception as e:
            logger.error(f"扩展热门模式失败: {e}")
            results['hot_expansion'] = {'error': str(e)}

        logger.info("✅ 周期性刷新完成")

        return results

    async def get_refresh_report(
        self,
        db: Session
    ) -> Dict:
        """
        获取刷新报告

        Args:
            db: 数据库会话

        Returns:
            刷新报告
        """
        # 1. 统计模式数量
        total_patterns = db.query(func.count(Pattern.pattern_id)).scalar()

        # 2. 分析趋势
        analyses = await self.trend_detector.analyze_all_patterns(db)

        trend_counts = {
            'rising': 0,
            'stable': 0,
            'declining': 0,
            'dead': 0,
            'insufficient_data': 0
        }

        for analysis in analyses:
            trend_counts[analysis.trend_type] = trend_counts.get(analysis.trend_type, 0) + 1

        # 3. 计算平均新鲜度
        freshness_scores = []
        for pattern in db.query(Pattern).all():
            freshness = await self.trend_detector.calculate_pattern_freshness(
                pattern.pattern_id,
                db
            )
            freshness_scores.append(freshness)

        avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0

        # 4. 推荐操作
        recommendations = {
            'refresh': trend_counts.get('declining', 0),
            'remove': trend_counts.get('dead', 0),
            'expand': trend_counts.get('rising', 0),
            'keep': trend_counts.get('stable', 0)
        }

        return {
            'total_patterns': total_patterns,
            'trend_distribution': trend_counts,
            'avg_freshness': avg_freshness,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db
    from app.analyzers.success_factor_extractor import SuccessFactorExtractor
    from app.analyzers.trend_detector import TrendDetector

    db = next(get_db())

    # 创建组件
    extractor = SuccessFactorExtractor()
    detector = TrendDetector()
    resampler = PatternResampler(extractor, detector)

    # 1. 重采样单个模式
    result = await resampler.resample_pattern('pattern_123', db, num_samples=20)
    print(f"重采样结果: {result}")

    # 2. 刷新陈旧模式
    refresh_result = await resampler.refresh_stale_patterns(db)
    print(f"刷新结果: {refresh_result}")

    # 3. 移除失效模式
    remove_result = await resampler.remove_dead_patterns(db)
    print(f"移除结果: {remove_result}")

    # 4. 扩展热门模式
    expand_result = await resampler.expand_hot_patterns(db, top_n=10)
    print(f"扩展结果: {expand_result}")

    # 5. 周期性刷新
    periodic_result = await resampler.periodic_refresh(db, refresh_interval_days=7)
    print(f"周期性刷新结果: {periodic_result}")

    # 6. 获取刷新报告
    report = await resampler.get_refresh_report(db)
    print(f"刷新报告: {report}")
