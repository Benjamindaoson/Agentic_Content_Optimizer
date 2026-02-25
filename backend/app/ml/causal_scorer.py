"""
CausalScorer: 因果奖励模型 (Stage 2)

核心目标：剥离“背景流量”和“混杂因素”，计算纯粹由策略（Hook/Body/CTA）产生的因果增益。
使用基于残差的因果推断思想。
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CausalInsight:
    observed_reward: float
    estimated_baseline: float
    causal_lift: float
    confounder_impact: Dict[str, float]

class CausalScorer:
    """
    因果评分器
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # 模拟混杂因素权重：发布者粉丝量、发布时段活跃度、品类热度
        self.confounder_weights = {
            "follower_count": 0.5,
            "peak_hour": 0.3,
            "category_trend": 0.2
        }

    def estimate_causal_reward(
        self,
        metrics: Dict[str, float],
        context: Dict[str, Any],
        strategy_action: Dict[str, Any]
    ) -> CausalInsight:
        """
        计算因果增益
        
        Lift = Observed - Baseline(Confounders)
        """
        # 1. 计算背景基线奖励 (Baseline)
        # 假设：Baseline = f(粉丝量, 时间, 品类)
        follower_factor = self._normalize_followers(context.get("follower_count", 0))
        hour_factor = self._get_hour_factor(context.get("publish_hour", 12))
        trend_factor = context.get("category_baseline_ctr", 0.05)
        
        baseline = (
            self.confounder_weights["follower_count"] * follower_factor +
            self.confounder_weights["peak_hour"] * hour_factor +
            self.confounder_weights["category_trend"] * (trend_factor / 0.1) # 简单归一化
        )
        
        # 2. 观察到的总奖励
        observed = metrics.get("engagement_rate", 0.0)
        
        # 3. 计算因果增益 (Causal Lift)
        # 我们使用简单的加性模型：Causal Lift = Observed - Baseline
        # 在真实 Stage 3 中，这里会使用 Double ML (DML) 逻辑
        causal_lift = observed - baseline
        
        # 4. 统计混杂因素影响
        impacts = {
            "social_capital": follower_factor * self.confounder_weights["follower_count"],
            "timing_lucky": hour_factor * self.confounder_weights["peak_hour"],
            "market_tide": trend_factor
        }
        
        return CausalInsight(
            observed_reward=float(observed),
            estimated_baseline=float(baseline),
            causal_lift=float(causal_lift),
            confounder_impact=impacts
        )

    def _normalize_followers(self, count: int) -> float:
        """对数归一化粉丝影响"""
        if count <= 0: return 0.0
        # 1k 粉丝左右开始有明显背景流量
        return float(np.clip(np.log10(count) / 6.0, 0, 1.0)) # 假设 1M 粉丝为 1.0

    def _get_hour_factor(self, hour: int) -> float:
        """简单的黄金时段评分"""
        # 晚 18:00 - 22:00 是峰值
        if 18 <= hour <= 22: return 1.0
        if 12 <= hour <= 14: return 0.7
        return 0.3
