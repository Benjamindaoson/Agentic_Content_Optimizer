"""
在线学习循环 - GRPO Online Learning Loop

实现持续的模型改进闭环：
1. 定期收集已发布内容的真实指标
2. 触发 GRPO 训练更新策略
3. 反馈到 Thompson Sampling
4. 持续优化内容生成质量
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session

from app.ml.rl.online_metrics_collector import OnlineMetricsCollector
from app.ml.rl.grpo_trainer import GRPOTrainer, TrainingResult
from app.db import get_db, Generation, Pattern

logger = logging.getLogger(__name__)


@dataclass
class LearningLoopConfig:
    """学习循环配置"""
    # 收集配置
    collection_interval_hours: int = 6  # 每6小时收集一次
    collection_lookback_days: int = 7  # 收集最近7天的数据

    # 训练配置
    training_interval_hours: int = 24  # 每24小时训练一次
    min_samples_per_pattern: int = 3  # 每个模式最少3个样本
    training_lookback_days: int = 7  # 训练数据窗口7天

    # 性能配置
    max_concurrent_collections: int = 10  # 最大并发收集数
    enable_auto_training: bool = True  # 是否自动触发训练


@dataclass
class LearningLoopStatus:
    """学习循环状态"""
    is_running: bool
    last_collection_at: Optional[datetime]
    last_training_at: Optional[datetime]
    next_collection_at: Optional[datetime]
    next_training_at: Optional[datetime]
    total_collections: int
    total_trainings: int
    total_samples_collected: int
    total_patterns_updated: int
    avg_improvement: float


class OnlineLearningLoop:
    """
    在线学习循环

    核心功能：
    1. 定期收集线上指标（每6小时）
    2. 定期触发 GRPO 训练（每24小时）
    3. 自动更新 Thompson Sampling 策略
    4. 提供监控和统计接口
    """

    def __init__(
        self,
        config: Optional[LearningLoopConfig] = None,
        metrics_collector: Optional[OnlineMetricsCollector] = None,
        grpo_trainer: Optional[GRPOTrainer] = None
    ):
        """初始化在线学习循环

        Args:
            config: 学习循环配置
            metrics_collector: 指标收集器
            grpo_trainer: GRPO 训练器
        """
        self.config = config or LearningLoopConfig()
        self.metrics_collector = metrics_collector or OnlineMetricsCollector()
        self.grpo_trainer = grpo_trainer or GRPOTrainer(self.metrics_collector)

        # 状态
        self.is_running = False
        self.last_collection_at: Optional[datetime] = None
        self.last_training_at: Optional[datetime] = None
        self.total_collections = 0
        self.total_trainings = 0
        self.total_samples_collected = 0
        self.total_patterns_updated = 0
        self.avg_improvement = 0.0

        # 任务
        self._collection_task: Optional[asyncio.Task] = None
        self._training_task: Optional[asyncio.Task] = None

        logger.info("OnlineLearningLoop initialized")

    async def start(self):
        """启动学习循环"""
        if self.is_running:
            logger.warning("Learning loop is already running")
            return

        self.is_running = True
        logger.info("Starting online learning loop...")

        # 启动收集任务
        self._collection_task = asyncio.create_task(self._collection_loop())

        # 启动训练任务
        if self.config.enable_auto_training:
            self._training_task = asyncio.create_task(self._training_loop())

        logger.info("Online learning loop started")

    async def stop(self):
        """停止学习循环"""
        if not self.is_running:
            logger.warning("Learning loop is not running")
            return

        self.is_running = False
        logger.info("Stopping online learning loop...")

        # 取消任务
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

        if self._training_task:
            self._training_task.cancel()
            try:
                await self._training_task
            except asyncio.CancelledError:
                pass

        logger.info("Online learning loop stopped")

    async def _collection_loop(self):
        """指标收集循环"""
        logger.info("Metrics collection loop started")

        while self.is_running:
            try:
                # 执行收集
                await self._run_collection()

                # 等待下一次收集
                await asyncio.sleep(self.config.collection_interval_hours * 3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Collection loop error: {e}", exc_info=True)
                # 出错后等待一段时间再重试
                await asyncio.sleep(300)  # 5分钟

    async def _training_loop(self):
        """训练循环"""
        logger.info("Training loop started")

        while self.is_running:
            try:
                # 执行训练
                await self._run_training()

                # 等待下一次训练
                await asyncio.sleep(self.config.training_interval_hours * 3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Training loop error: {e}", exc_info=True)
                # 出错后等待一段时间再重试
                await asyncio.sleep(600)  # 10分钟

    async def _run_collection(self):
        """执行一次指标收集"""
        logger.info("Running metrics collection...")
        start_time = datetime.now()

        try:
            # 获取数据库会话
            db = next(get_db())

            # 收集最近发布内容的指标
            snapshots = await self.metrics_collector.collect_recent_published(
                days=self.config.collection_lookback_days,
                db=db
            )

            # 更新统计
            self.last_collection_at = datetime.now()
            self.total_collections += 1
            self.total_samples_collected += len(snapshots)

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Metrics collection completed: "
                f"collected={len(snapshots)}, "
                f"elapsed={elapsed:.2f}s"
            )

        except Exception as e:
            logger.error(f"Metrics collection failed: {e}", exc_info=True)
        finally:
            if db:
                db.close()

    async def _run_training(self):
        """执行一次 GRPO 训练"""
        logger.info("Running GRPO training...")
        start_time = datetime.now()

        try:
            # 获取数据库会话
            db = next(get_db())

            # 执行训练
            result: TrainingResult = await self.grpo_trainer.train(
                days=self.config.training_lookback_days,
                min_samples_per_pattern=self.config.min_samples_per_pattern,
                db=db
            )

            # 更新统计
            self.last_training_at = datetime.now()
            self.total_trainings += 1
            self.total_patterns_updated += len(result.pattern_updates)

            # 更新平均提升（指数移动平均）
            alpha = 0.3
            self.avg_improvement = (
                alpha * result.avg_improvement +
                (1 - alpha) * self.avg_improvement
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"GRPO training completed: "
                f"run_id={result.run_id}, "
                f"samples={result.total_samples}, "
                f"patterns_updated={len(result.pattern_updates)}, "
                f"avg_improvement={result.avg_improvement:.4f}, "
                f"elapsed={elapsed:.2f}s"
            )

        except Exception as e:
            logger.error(f"GRPO training failed: {e}", exc_info=True)
        finally:
            if db:
                db.close()

    async def trigger_collection(self) -> Dict[str, Any]:
        """手动触发一次指标收集

        Returns:
            收集结果
        """
        logger.info("Manually triggering metrics collection...")

        try:
            db = next(get_db())

            snapshots = await self.metrics_collector.collect_recent_published(
                days=self.config.collection_lookback_days,
                db=db
            )

            self.last_collection_at = datetime.now()
            self.total_collections += 1
            self.total_samples_collected += len(snapshots)

            return {
                'status': 'success',
                'collected_count': len(snapshots),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Manual collection failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        finally:
            if db:
                db.close()

    async def trigger_training(self) -> Dict[str, Any]:
        """手动触发一次 GRPO 训练

        Returns:
            训练结果
        """
        logger.info("Manually triggering GRPO training...")

        try:
            db = next(get_db())

            result: TrainingResult = await self.grpo_trainer.train(
                days=self.config.training_lookback_days,
                min_samples_per_pattern=self.config.min_samples_per_pattern,
                db=db
            )

            self.last_training_at = datetime.now()
            self.total_trainings += 1
            self.total_patterns_updated += len(result.pattern_updates)

            return {
                'status': 'success',
                'run_id': result.run_id,
                'total_samples': result.total_samples,
                'patterns_updated': len(result.pattern_updates),
                'avg_improvement': result.avg_improvement,
                'training_time': result.training_time,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Manual training failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        finally:
            if db:
                db.close()

    def get_status(self) -> LearningLoopStatus:
        """获取学习循环状态

        Returns:
            学习循环状态
        """
        # 计算下次执行时间
        next_collection_at = None
        if self.last_collection_at:
            next_collection_at = self.last_collection_at + timedelta(
                hours=self.config.collection_interval_hours
            )

        next_training_at = None
        if self.last_training_at:
            next_training_at = self.last_training_at + timedelta(
                hours=self.config.training_interval_hours
            )

        return LearningLoopStatus(
            is_running=self.is_running,
            last_collection_at=self.last_collection_at,
            last_training_at=self.last_training_at,
            next_collection_at=next_collection_at,
            next_training_at=next_training_at,
            total_collections=self.total_collections,
            total_trainings=self.total_trainings,
            total_samples_collected=self.total_samples_collected,
            total_patterns_updated=self.total_patterns_updated,
            avg_improvement=self.avg_improvement
        )

    async def get_recent_performance(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取最近的性能统计

        Args:
            days: 统计天数

        Returns:
            性能统计
        """
        try:
            db = next(get_db())

            # 查询最近发布的内容
            cutoff_date = datetime.now() - timedelta(days=days)

            generations = db.query(Generation).filter(
                Generation.status == 'published',
                Generation.published_at >= cutoff_date
            ).all()

            if not generations:
                return {
                    'status': 'no_data',
                    'period_days': days,
                    'total_generations': 0
                }

            # 统计各模式的表现
            pattern_stats = {}

            for gen in generations:
                if not gen.pattern_id:
                    continue

                if gen.pattern_id not in pattern_stats:
                    pattern_stats[gen.pattern_id] = {
                        'count': 0,
                        'avg_viral_score': 0.0,
                        'success_count': 0
                    }

                # 查询最新指标
                from app.db import OnlineMetrics
                metric = db.query(OnlineMetrics).filter_by(
                    generation_id=gen.generation_id
                ).order_by(OnlineMetrics.collected_at.desc()).first()

                if metric:
                    pattern_stats[gen.pattern_id]['count'] += 1
                    pattern_stats[gen.pattern_id]['avg_viral_score'] += metric.viral_score
                    if metric.viral_score > 0.7:
                        pattern_stats[gen.pattern_id]['success_count'] += 1

            # 计算平均值
            for pattern_id, stats in pattern_stats.items():
                if stats['count'] > 0:
                    stats['avg_viral_score'] /= stats['count']
                    stats['success_rate'] = stats['success_count'] / stats['count']

            # 整体统计
            total_generations = len(generations)
            total_with_metrics = sum(s['count'] for s in pattern_stats.values())
            avg_viral_score = (
                sum(s['avg_viral_score'] * s['count'] for s in pattern_stats.values()) /
                max(total_with_metrics, 1)
            )
            total_success = sum(s['success_count'] for s in pattern_stats.values())
            overall_success_rate = total_success / max(total_with_metrics, 1)

            return {
                'status': 'success',
                'period_days': days,
                'total_generations': total_generations,
                'total_with_metrics': total_with_metrics,
                'overall_stats': {
                    'avg_viral_score': round(avg_viral_score, 4),
                    'success_rate': round(overall_success_rate, 4),
                    'total_success': total_success
                },
                'pattern_stats': {
                    pattern_id: {
                        'count': stats['count'],
                        'avg_viral_score': round(stats['avg_viral_score'], 4),
                        'success_rate': round(stats.get('success_rate', 0), 4)
                    }
                    for pattern_id, stats in pattern_stats.items()
                },
                'top_patterns': sorted(
                    [
                        {
                            'pattern_id': pattern_id,
                            'avg_viral_score': stats['avg_viral_score'],
                            'count': stats['count']
                        }
                        for pattern_id, stats in pattern_stats.items()
                    ],
                    key=lambda x: x['avg_viral_score'],
                    reverse=True
                )[:5]
            }

        except Exception as e:
            logger.error(f"Get recent performance failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }
        finally:
            if db:
                db.close()


# 全局实例（单例）
_learning_loop_instance: Optional[OnlineLearningLoop] = None


def get_learning_loop() -> OnlineLearningLoop:
    """获取学习循环实例（单例）

    Returns:
        OnlineLearningLoop 实例
    """
    global _learning_loop_instance

    if _learning_loop_instance is None:
        _learning_loop_instance = OnlineLearningLoop()
        logger.info("Global OnlineLearningLoop instance created")

    return _learning_loop_instance
