"""
GRPO 训练器

基于线上真实指标进行 Group Relative Policy Optimization 训练
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from sqlalchemy.orm import Session

from app.db import Pattern, Generation, OnlineMetrics, GRPORun
from app.ml.rl.online_metrics_collector import OnlineMetricsCollector


@dataclass
class TrainingBatch:
    """训练批次"""
    pattern_id: str
    generations: List[Dict[str, Any]]  # 生成记录 + 指标
    avg_reward: float
    reward_std: float
    sample_size: int


@dataclass
class TrainingResult:
    """训练结果"""
    run_id: str
    pattern_updates: List[Dict[str, Any]]
    total_samples: int
    avg_improvement: float
    training_time: float


class GRPOTrainer:
    """
    GRPO 训练器

    核心功能：
    1. 收集线上指标作为奖励信号
    2. 按模式分组计算相对奖励
    3. 更新模式的成功率和先验
    4. 反哺 Thompson Sampling
    """

    def __init__(
        self,
        metrics_collector: Optional[OnlineMetricsCollector] = None
    ):
        self.metrics_collector = metrics_collector or OnlineMetricsCollector()

    async def train(
        self,
        days: int = 7,
        min_samples_per_pattern: int = 3,
        db: Session = None
    ) -> TrainingResult:
        """
        执行 GRPO 训练

        Args:
            days: 训练数据时间窗口（天）
            min_samples_per_pattern: 每个模式最小样本数
            db: 数据库会话

        Returns:
            训练结果
        """
        start_time = datetime.now()

        # 1. 收集训练数据
        training_batches = await self._collect_training_data(
            days=days,
            min_samples_per_pattern=min_samples_per_pattern,
            db=db
        )

        if not training_batches:
            return TrainingResult(
                run_id='',
                pattern_updates=[],
                total_samples=0,
                avg_improvement=0.0,
                training_time=0.0
            )

        # 2. 计算相对奖励
        batches_with_relative_rewards = self._calculate_relative_rewards(
            training_batches
        )

        # 3. 更新模式
        pattern_updates = await self._update_patterns(
            batches_with_relative_rewards,
            db=db
        )

        # 4. 保存训练记录
        end_time = datetime.now()
        training_time = (end_time - start_time).total_seconds()

        run_id = await self._save_training_run(
            pattern_updates=pattern_updates,
            total_samples=sum(b.sample_size for b in training_batches),
            training_time=training_time,
            db=db
        )

        # 5. 计算平均提升
        avg_improvement = np.mean([
            u['improvement'] for u in pattern_updates
        ]) if pattern_updates else 0.0

        return TrainingResult(
            run_id=run_id,
            pattern_updates=pattern_updates,
            total_samples=sum(b.sample_size for b in training_batches),
            avg_improvement=avg_improvement,
            training_time=training_time
        )

    async def _collect_training_data(
        self,
        days: int,
        min_samples_per_pattern: int,
        db: Session
    ) -> List[TrainingBatch]:
        """收集训练数据"""
        # 收集最近发布内容的指标
        snapshots = await self.metrics_collector.collect_recent_published(
            days=days,
            db=db
        )

        if not snapshots:
            return []

        # 按模式分组
        pattern_groups: Dict[str, List[Dict[str, Any]]] = {}

        for snapshot in snapshots:
            # 查询生成记录
            generation = db.query(Generation).filter_by(
                generation_id=snapshot.generation_id
            ).first()

            if not generation or not generation.pattern_id:
                continue

            pattern_id = generation.pattern_id

            if pattern_id not in pattern_groups:
                pattern_groups[pattern_id] = []

            pattern_groups[pattern_id].append({
                'generation_id': generation.generation_id,
                'pattern_id': pattern_id,
                'viral_score': snapshot.viral_score,
                'engagement_rate': snapshot.engagement_rate,
                'velocity_score': snapshot.velocity_score,
                'predicted_viral_score': snapshot.predicted_viral_score,
                'actual_vs_predicted': snapshot.actual_vs_predicted
            })

        # 过滤样本数不足的模式
        training_batches = []

        for pattern_id, generations in pattern_groups.items():
            if len(generations) < min_samples_per_pattern:
                continue

            # 计算奖励（使用 viral_score）
            rewards = [g['viral_score'] for g in generations]
            avg_reward = np.mean(rewards)
            reward_std = np.std(rewards)

            batch = TrainingBatch(
                pattern_id=pattern_id,
                generations=generations,
                avg_reward=avg_reward,
                reward_std=reward_std,
                sample_size=len(generations)
            )

            training_batches.append(batch)

        return training_batches

    def _calculate_relative_rewards(
        self,
        batches: List[TrainingBatch]
    ) -> List[TrainingBatch]:
        """
        计算相对奖励（GRPO 核心）

        相对奖励 = (当前奖励 - 组平均奖励) / 组标准差
        """
        # 计算全局统计
        all_rewards = []
        for batch in batches:
            all_rewards.extend([g['viral_score'] for g in batch.generations])

        global_mean = np.mean(all_rewards)
        global_std = np.std(all_rewards)

        # 计算每个批次的相对奖励
        for batch in batches:
            for gen in batch.generations:
                # 相对奖励
                relative_reward = (
                    (gen['viral_score'] - global_mean) / max(global_std, 0.01)
                )
                gen['relative_reward'] = relative_reward

                # 优势（Advantage）
                advantage = (
                    gen['viral_score'] - batch.avg_reward
                ) / max(batch.reward_std, 0.01)
                gen['advantage'] = advantage

        return batches

    async def _update_patterns(
        self,
        batches: List[TrainingBatch],
        db: Session
    ) -> List[Dict[str, Any]]:
        """更新模式的成功率和先验"""
        pattern_updates = []

        for batch in batches:
            # 查询模式
            pattern = db.query(Pattern).filter_by(
                pattern_id=batch.pattern_id
            ).first()

            if not pattern:
                continue

            # 保存旧值
            old_success_rate = pattern.success_rate or 0.5
            old_sample_size = pattern.sample_size or 0

            # 计算新的成功率
            # 使用贝叶斯更新：结合先验和新数据
            new_samples = batch.sample_size
            new_success_rate = batch.avg_reward

            # 贝叶斯更新（加权平均）
            total_samples = old_sample_size + new_samples
            updated_success_rate = (
                (old_success_rate * old_sample_size + new_success_rate * new_samples) /
                total_samples
            )

            # 更新模式
            pattern.success_rate = updated_success_rate
            pattern.sample_size = total_samples
            pattern.avg_viral_score = updated_success_rate
            pattern.last_trained_at = datetime.now()

            # 更新 Thompson Sampling 先验
            # Beta 分布参数：alpha = 成功数, beta = 失败数
            successes = updated_success_rate * total_samples
            failures = (1 - updated_success_rate) * total_samples

            pattern.thompson_alpha = max(successes, 1.0)
            pattern.thompson_beta = max(failures, 1.0)

            db.commit()

            # 记录更新
            improvement = updated_success_rate - old_success_rate

            pattern_updates.append({
                'pattern_id': batch.pattern_id,
                'old_success_rate': old_success_rate,
                'new_success_rate': updated_success_rate,
                'improvement': improvement,
                'old_sample_size': old_sample_size,
                'new_sample_size': total_samples,
                'thompson_alpha': pattern.thompson_alpha,
                'thompson_beta': pattern.thompson_beta
            })

        return pattern_updates

    async def _save_training_run(
        self,
        pattern_updates: List[Dict[str, Any]],
        total_samples: int,
        training_time: float,
        db: Session
    ) -> str:
        """保存训练记录"""
        import uuid

        run_id = str(uuid.uuid4())

        # 计算统计
        avg_improvement = np.mean([
            u['improvement'] for u in pattern_updates
        ]) if pattern_updates else 0.0

        patterns_updated = len(pattern_updates)

        # 创建训练记录
        run = GRPORun(
            run_id=run_id,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            total_samples=total_samples,
            patterns_updated=patterns_updated,
            avg_improvement=avg_improvement,
            training_params={
                'training_time': training_time,
                'pattern_updates': pattern_updates
            },
            status='completed'
        )

        db.add(run)
        db.commit()

        return run_id

    async def evaluate_prediction_accuracy(
        self,
        days: int = 7,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        评估预测准确性

        Args:
            days: 评估时间窗口（天）
            db: 数据库会话

        Returns:
            准确性报告
        """
        # 收集最近的指标
        snapshots = await self.metrics_collector.collect_recent_published(
            days=days,
            db=db
        )

        if not snapshots:
            return {
                'status': 'no_data',
                'total_samples': 0
            }

        # 计算准确性指标
        errors = []
        absolute_errors = []
        relative_errors = []

        for snapshot in snapshots:
            predicted = snapshot.predicted_viral_score
            actual = snapshot.viral_score

            error = actual - predicted
            absolute_error = abs(error)
            relative_error = absolute_error / max(actual, 0.01)

            errors.append(error)
            absolute_errors.append(absolute_error)
            relative_errors.append(relative_error)

        # 统计
        mae = np.mean(absolute_errors)  # Mean Absolute Error
        rmse = np.sqrt(np.mean([e**2 for e in errors]))  # Root Mean Square Error
        mape = np.mean(relative_errors) * 100  # Mean Absolute Percentage Error

        # 准确率（误差 < 20%）
        accurate_count = sum(1 for e in relative_errors if e < 0.2)
        accuracy_rate = accurate_count / len(relative_errors)

        # 过高/过低预测
        overestimate_count = sum(1 for e in errors if e < -0.1)
        underestimate_count = sum(1 for e in errors if e > 0.1)

        return {
            'status': 'success',
            'total_samples': len(snapshots),
            'metrics': {
                'mae': mae,
                'rmse': rmse,
                'mape': mape,
                'accuracy_rate': accuracy_rate
            },
            'distribution': {
                'overestimate_count': overestimate_count,
                'underestimate_count': underestimate_count,
                'accurate_count': accurate_count
            },
            'statistics': {
                'mean_error': np.mean(errors),
                'std_error': np.std(errors),
                'min_error': np.min(errors),
                'max_error': np.max(errors)
            }
        }

    async def get_training_history(
        self,
        limit: int = 10,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        获取训练历史

        Args:
            limit: 返回数量
            db: 数据库会话

        Returns:
            训练历史列表
        """
        if not db:
            return []

        runs = db.query(GRPORun).order_by(
            GRPORun.started_at.desc()
        ).limit(limit).all()

        history = []

        for run in runs:
            history.append({
                'run_id': run.run_id,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'finished_at': run.finished_at.isoformat() if run.finished_at else None,
                'total_samples': run.total_samples,
                'patterns_updated': run.patterns_updated,
                'avg_improvement': run.avg_improvement,
                'status': run.status
            })

        return history
