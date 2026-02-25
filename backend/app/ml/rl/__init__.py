"""
强化学习模块初始化
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2
    from app.ml.rl.diversity_scorer import DiversityScorer
    from app.ml.rl.thompson_sampling import ThompsonSamplingSelector
    from app.ml.rl.online_metrics_collector import OnlineMetricsCollector, MetricsSnapshot
    from app.ml.rl.grpo_trainer import GRPOTrainer, TrainingBatch, TrainingResult


def __getattr__(name: str):
    if name == "HybridRewardModelV2":
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2
        return HybridRewardModelV2
    if name == "DiversityScorer":
        from app.ml.rl.diversity_scorer import DiversityScorer
        return DiversityScorer
    if name == "ThompsonSamplingSelector":
        from app.ml.rl.thompson_sampling import ThompsonSamplingSelector
        return ThompsonSamplingSelector
    if name in {"OnlineMetricsCollector", "MetricsSnapshot"}:
        from app.ml.rl.online_metrics_collector import OnlineMetricsCollector, MetricsSnapshot
        mapping = {
            "OnlineMetricsCollector": OnlineMetricsCollector,
            "MetricsSnapshot": MetricsSnapshot,
        }
        return mapping[name]
    if name in {"GRPOTrainer", "TrainingBatch", "TrainingResult"}:
        from app.ml.rl.grpo_trainer import GRPOTrainer, TrainingBatch, TrainingResult
        mapping = {
            "GRPOTrainer": GRPOTrainer,
            "TrainingBatch": TrainingBatch,
            "TrainingResult": TrainingResult,
        }
        return mapping[name]
    raise AttributeError(name)

__all__ = [
    # 奖励模型
    'HybridRewardModelV2',

    # 多样性评分
    'DiversityScorer',

    # Thompson Sampling
    'ThompsonSamplingSelector',

    # 线上指标收集
    'OnlineMetricsCollector',
    'MetricsSnapshot',

    # GRPO 训练
    'GRPOTrainer',
    'TrainingBatch',
    'TrainingResult'
]
