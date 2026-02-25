"""
Legacy RewardModel - alias for HybridRewardModelV2.
Use HybridRewardModelV2 for new code.
"""
from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2 as RewardModel

__all__ = ["RewardModel"]
