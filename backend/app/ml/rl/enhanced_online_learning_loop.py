"""
增强的在线学习循环 - 集成 GRPO 策略学习 + DPO 模型微调

完整流程：
1. 线上数据收集（每 6 小时）
2. GRPO 策略更新（每 24 小时）
3. DPO 模型微调（每 7 天）
4. 持续优化反馈循环
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session

from app.ml.rl.online_metrics_collector import OnlineMetricsCollector
from app.ml.rl.grpo_trainer import GRPOTrainer
from app.training.finetune_orchestrator import FinetuneOrchestrator, FinetuneConfig

logger = logging.getLogger(__name__)


@dataclass
class EnhancedLearningConfig:
    """增强学习循环配置"""
    # GRPO 策略学习
    grpo_collection_interval_hours: int = 6  # 每 6 小时收集指标
    grpo_training_interval_hours: int = 24  # 每 24 小时训练策略

    # DPO 模型微调
    dpo_finetune_interval_days: int = 7  # 每 7 天微调模型
    dpo_min_samples: int = 1000  # 最小样本数
    dpo_auto_deploy: bool = False  # 是否自动部署

    # 触发条件
    performance_drop_threshold: float = 0.1  # 性能下降 10% 触发微调
    enable_auto_finetune: bool = True  # 是否自动触发微调


class EnhancedOnlineLearningLoop:
    """
    增强的在线学习循环

    两层学习机制：
    1. 快速层：GRPO 策略学习（每天）
       - 学习哪些策略组合效果好
       - 调整 Thompson Sampling 概率分布
       - 不改变模型本身

    2. 慢速层：DPO 模型微调（每周）
       - 改进模型本身的生成能力
       - 基于真实偏好数据微调
       - 提升整体内容质量
    """

    def __init__(
        self,
        config: Optional[EnhancedLearningConfig] = None,
        db: Optional[Session] = None
    ):
        """初始化增强学习循环

        Args:
            config: 学习循环配置
            db: 数据库会话
        """
        self.config = config or EnhancedLearningConfig()
        self.db = db

        # 初始化组件
        self.metrics_collector = OnlineMetricsCollector()
        self.grpo_trainer = GRPOTrainer(self.metrics_collector)

        # 微调编排器
        finetune_config = FinetuneConfig(
            collection_days=self.config.dpo_finetune_interval_days,
            min_samples=self.config.dpo_min_samples,
            auto_deploy=self.config.dpo_auto_deploy
        )
        self.finetune_orchestrator = FinetuneOrchestrator(
            config=finetune_config,
            db=db
        )

        # 状态
        self.is_running = False
        self.last_grpo_training: Optional[datetime] = None
        self.last_dpo_finetune: Optional[datetime] = None
        self.baseline_performance: float = 0.0

        # 任务
        self._grpo_task: Optional[asyncio.Task] = None
        self._dpo_task: Optional[asyncio.Task] = None

        logger.info("EnhancedOnlineLearningLoop initialized")

    async def start(self):
        """启动学习循环"""
        if self.is_running:
            logger.warning("Learning loop already running")
            return

        self.is_running = True
        logger.info("Starting enhanced learning loop...")

        # 启动 GRPO 策略学习任务
        self._grpo_task = asyncio.create_task(self._grpo_learning_loop())

        # 启动 DPO 模型微调任务
        if self.config.enable_auto_finetune:
            self._dpo_task = asyncio.create_task(self._dpo_finetune_loop())

        logger.info("Enhanced learning loop started")

    async def stop(self):
        """停止学习循环"""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping enhanced learning loop...")

        # 取消任务
        if self._grpo_task:
            self._grpo_task.cancel()
        if self._dpo_task:
            self._dpo_task.cancel()

        logger.info("Enhanced learning loop stopped")

    async def _grpo_learning_loop(self):
        """GRPO 策略学习循环（快速层）

        每 24 小时运行一次，学习哪些策略组合效果好
        """
        logger.info("GRPO learning loop started")

        while self.is_running:
            try:
                # 等待到下一次训练时间
                await asyncio.sleep(
                    self.config.grpo_training_interval_hours * 3600
                )

                if not self.is_running:
                    break

                logger.info("=" * 80)
                logger.info("Running GRPO strategy learning...")
                logger.info("=" * 80)

                # 执行 GRPO 训练
                result = await self.grpo_trainer.train(
                    days=7,
                    min_samples_per_pattern=3,
                    db=self.db
                )

                self.last_grpo_training = datetime.now()

                logger.info(
                    f"✓ GRPO training completed: "
                    f"{result.total_samples} samples, "
                    f"{len(result.pattern_updates)} patterns updated, "
                    f"avg improvement: {result.avg_improvement:.2%}"
                )

            except asyncio.CancelledError:
                logger.info("GRPO learning loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in GRPO learning loop: {e}", exc_info=True)
                # 继续运行，不中断循环

    async def _dpo_finetune_loop(self):
        """DPO 模型微调循环（慢速层）

        每 7 天运行一次，改进模型本身的生成能力
        """
        logger.info("DPO finetune loop started")

        while self.is_running:
            try:
                # 等待到下一次微调时间
                await asyncio.sleep(
                    self.config.dpo_finetune_interval_days * 24 * 3600
                )

                if not self.is_running:
                    break

                # 检查是否需要微调
                should_finetune = await self._should_trigger_finetune()

                if not should_finetune:
                    logger.info("Skipping finetune: conditions not met")
                    continue

                logger.info("=" * 80)
                logger.info("Running DPO model finetuning...")
                logger.info("=" * 80)

                # 执行完整的微调周期
                result = await self.finetune_orchestrator.run_full_cycle()

                self.last_dpo_finetune = datetime.now()

                if result["status"] == "success":
                    logger.info(
                        f"✓ DPO finetuning completed in {result['duration_seconds']:.1f}s"
                    )
                    logger.info(f"  - Preference pairs: {result['preference_pairs']['count']}")
                    logger.info(f"  - Evaluation score: {result['evaluation']['overall_score']:.2f}")
                    logger.info(f"  - Deployment: {result['deployment']['status']}")
                else:
                    logger.error(f"✗ DPO finetuning failed: {result.get('error')}")

            except asyncio.CancelledError:
                logger.info("DPO finetune loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in DPO finetune loop: {e}", exc_info=True)
                # 继续运行，不中断循环

    async def _should_trigger_finetune(self) -> bool:
        """判断是否应该触发微调

        触发条件：
        1. 距离上次微调超过 N 天
        2. 收集到足够的新样本
        3. 性能下降超过阈值

        Returns:
            是否应该触发微调
        """
        # 条件 1：时间间隔
        if self.last_dpo_finetune:
            days_since_last = (datetime.now() - self.last_dpo_finetune).days
            if days_since_last < self.config.dpo_finetune_interval_days:
                logger.info(f"Too soon since last finetune ({days_since_last} days)")
                return False

        # 条件 2：样本数量 — query DB for actual count
        try:
            from app.db import get_db, Generation
            from sqlalchemy import func
            db = next(get_db())
            since = self.last_dpo_finetune or (datetime.now() - timedelta(days=self.config.dpo_finetune_interval_days))
            new_samples_count = db.query(func.count(Generation.id)).filter(
                Generation.created_at >= since
            ).scalar() or 0
            db.close()
        except Exception as e:
            logger.warning(f"Failed to query sample count: {e}")
            new_samples_count = 0

        if new_samples_count < self.config.dpo_min_samples:
            logger.info(f"Insufficient samples ({new_samples_count}/{self.config.dpo_min_samples})")
            return False

        # 条件 3：性能下降
        current_performance = await self._get_current_performance()

        if self.baseline_performance > 0:
            performance_drop = (self.baseline_performance - current_performance) / self.baseline_performance

            if performance_drop > self.config.performance_drop_threshold:
                logger.info(f"Performance dropped by {performance_drop:.1%}, triggering finetune")
                return True

        # 更新基线性能
        if current_performance > self.baseline_performance:
            self.baseline_performance = current_performance

        return True  # 默认触发

    async def _get_current_performance(self) -> float:
        """获取当前系统性能 — query DB for average reward of recent episodes.

        Returns:
            性能分数（0-10）
        """
        try:
            from app.db import get_db, Generation
            from sqlalchemy import func
            db = next(get_db())
            avg_score = db.query(func.avg(Generation.quality_score)).filter(
                Generation.created_at >= datetime.now() - timedelta(days=7)
            ).scalar()
            db.close()
            if avg_score is not None:
                return float(avg_score)
        except Exception as e:
            logger.warning(f"Failed to query performance: {e}")
        return 5.0

    async def trigger_grpo_training(self) -> Dict[str, Any]:
        """手动触发 GRPO 训练

        Returns:
            训练结果
        """
        logger.info("Manually triggering GRPO training...")

        result = await self.grpo_trainer.train(
            days=7,
            min_samples_per_pattern=3,
            db=self.db
        )

        self.last_grpo_training = datetime.now()

        return {
            "status": "success",
            "total_samples": result.total_samples,
            "patterns_updated": len(result.pattern_updates),
            "avg_improvement": result.avg_improvement
        }

    async def trigger_dpo_finetune(self) -> Dict[str, Any]:
        """手动触发 DPO 微调

        Returns:
            微调结果
        """
        logger.info("Manually triggering DPO finetuning...")

        result = await self.finetune_orchestrator.run_full_cycle()

        self.last_dpo_finetune = datetime.now()

        return result

    def get_status(self) -> Dict[str, Any]:
        """获取学习循环状态

        Returns:
            状态信息
        """
        return {
            "is_running": self.is_running,
            "grpo_learning": {
                "last_training": self.last_grpo_training.isoformat() if self.last_grpo_training else None,
                "next_training": (
                    self.last_grpo_training + timedelta(hours=self.config.grpo_training_interval_hours)
                ).isoformat() if self.last_grpo_training else None,
                "interval_hours": self.config.grpo_training_interval_hours
            },
            "dpo_finetuning": {
                "last_finetune": self.last_dpo_finetune.isoformat() if self.last_dpo_finetune else None,
                "next_finetune": (
                    self.last_dpo_finetune + timedelta(days=self.config.dpo_finetune_interval_days)
                ).isoformat() if self.last_dpo_finetune else None,
                "interval_days": self.config.dpo_finetune_interval_days,
                "auto_deploy": self.config.dpo_auto_deploy
            },
            "performance": {
                "baseline": self.baseline_performance,
                "drop_threshold": self.config.performance_drop_threshold
            }
        }
