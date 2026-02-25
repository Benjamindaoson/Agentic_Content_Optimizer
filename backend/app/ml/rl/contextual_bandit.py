"""
Contextual Bandit — Thompson Sampling 的上下文感知升级

核心差异：原 Thompson Sampling 只看 (hook, body, cta) 的全局成功率，
Contextual Bandit 加入上下文特征后，能学习到：
- "护肤话题 + 女性受众 → 共鸣型 Hook 效果更好"
- "科技话题 + 晚间发布 → 数据型 Body 效果更好"

实现方式：LinUCB（Linear Upper Confidence Bound）
- 每个 action 维护一个线性模型 θ_a
- 根据上下文特征 x 预测 reward: r = θ_a^T * x + α * √(x^T A_a^{-1} x)
- α 控制探索-利用平衡
"""

import logging
import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextFeatures:
    """上下文特征向量"""
    topic_category: str = ""
    platform: str = "xiaohongshu"
    hour_of_day: int = 12
    day_of_week: int = 3
    audience_type: str = ""
    content_length: str = "medium"

    def to_vector(self) -> np.ndarray:
        """将上下文特征转换为数值向量"""
        features = []

        # 话题类别 one-hot（8 维）
        categories = ["护肤", "穿搭", "美食", "科技", "健身", "旅行", "母婴", "其他"]
        cat_vec = [0.0] * len(categories)
        for i, cat in enumerate(categories):
            if cat in self.topic_category:
                cat_vec[i] = 1.0
                break
        else:
            cat_vec[-1] = 1.0
        features.extend(cat_vec)

        # 平台 one-hot（4 维）
        platforms = ["xiaohongshu", "douyin", "tiktok", "kuaishou"]
        plat_vec = [1.0 if p == self.platform else 0.0 for p in platforms]
        features.extend(plat_vec)

        # 时段特征（3 维：正弦/余弦编码 + 是否工作时间）
        hour_rad = 2 * math.pi * self.hour_of_day / 24
        features.append(math.sin(hour_rad))
        features.append(math.cos(hour_rad))
        features.append(1.0 if 9 <= self.hour_of_day <= 22 else 0.0)

        # 星期特征（2 维：是否周末 + 正弦编码）
        features.append(1.0 if self.day_of_week >= 5 else 0.0)
        features.append(math.sin(2 * math.pi * self.day_of_week / 7))

        # 内容长度（3 维 one-hot）
        lengths = ["short", "medium", "long"]
        features.extend([1.0 if l == self.content_length else 0.0 for l in lengths])

        # bias 项
        features.append(1.0)

        return np.array(features, dtype=np.float64)

    @property
    def dim(self) -> int:
        return len(self.to_vector())


# 特征维度（固定）
CONTEXT_DIM = ContextFeatures().dim  # 8+4+3+2+3+1 = 21


@dataclass
class LinUCBArm:
    """LinUCB 的单个臂"""
    A: np.ndarray = field(default_factory=lambda: np.eye(CONTEXT_DIM))
    b: np.ndarray = field(default_factory=lambda: np.zeros(CONTEXT_DIM))
    n_pulls: int = 0

    @property
    def theta(self) -> np.ndarray:
        """当前参数估计"""
        try:
            return np.linalg.solve(self.A, self.b)
        except np.linalg.LinAlgError:
            return np.zeros(CONTEXT_DIM)


class ContextualBandit:
    """
    LinUCB Contextual Bandit

    向后兼容 Thompson Sampling 的接口，同时加入上下文感知能力。
    """

    def __init__(
        self,
        n_actions: int,
        alpha: float = 1.0,
        action_labels: Optional[List[str]] = None,
    ):
        self.n_actions = n_actions
        self.alpha = alpha
        self.action_labels = action_labels or [str(i) for i in range(n_actions)]
        self.arms: Dict[int, LinUCBArm] = {i: LinUCBArm() for i in range(n_actions)}
        self.total_pulls = 0

    def select_action(self, context: ContextFeatures) -> Tuple[int, float]:
        """
        选择动作（UCB 策略）。

        Returns:
            (action_index, ucb_score)
        """
        x = context.to_vector()
        best_action = 0
        best_score = -float("inf")

        for action_id, arm in self.arms.items():
            theta = arm.theta
            pred_reward = float(theta @ x)

            # UCB bonus
            A_inv = np.linalg.inv(arm.A)
            uncertainty = float(self.alpha * math.sqrt(x @ A_inv @ x))

            ucb_score = pred_reward + uncertainty

            if ucb_score > best_score:
                best_score = ucb_score
                best_action = action_id

        return best_action, best_score

    def update(self, action: int, context: ContextFeatures, reward: float):
        """更新臂的参数"""
        if action not in self.arms:
            logger.warning(f"Unknown action {action}, creating new arm")
            self.arms[action] = LinUCBArm()

        x = context.to_vector()
        arm = self.arms[action]
        arm.A += np.outer(x, x)
        arm.b += reward * x
        arm.n_pulls += 1
        self.total_pulls += 1

    def get_action_scores(self, context: ContextFeatures) -> Dict[int, float]:
        """获取所有动作的 UCB 分数"""
        x = context.to_vector()
        scores = {}
        for action_id, arm in self.arms.items():
            theta = arm.theta
            pred = float(theta @ x)
            A_inv = np.linalg.inv(arm.A)
            bonus = float(self.alpha * math.sqrt(x @ A_inv @ x))
            scores[action_id] = pred + bonus
        return scores

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于 Redis 持久化）"""
        arms_data = {}
        for action_id, arm in self.arms.items():
            arms_data[str(action_id)] = {
                "A": arm.A.tolist(),
                "b": arm.b.tolist(),
                "n_pulls": arm.n_pulls,
            }
        return {
            "n_actions": self.n_actions,
            "alpha": self.alpha,
            "total_pulls": self.total_pulls,
            "arms": arms_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextualBandit":
        """从字典反序列化"""
        bandit = cls(
            n_actions=data["n_actions"],
            alpha=data.get("alpha", 1.0),
        )
        bandit.total_pulls = data.get("total_pulls", 0)
        for action_str, arm_data in data.get("arms", {}).items():
            action_id = int(action_str)
            bandit.arms[action_id] = LinUCBArm(
                A=np.array(arm_data["A"]),
                b=np.array(arm_data["b"]),
                n_pulls=arm_data.get("n_pulls", 0),
            )
        return bandit


class HybridSelector:
    """
    混合选择器：Thompson Sampling（冷启动）+ Contextual Bandit（数据充足后）

    - 当某个 action 的拉取次数 < min_pulls_for_context 时，使用 Thompson Sampling
    - 当数据充足后，切换到 Contextual Bandit
    """

    def __init__(
        self,
        thompson_selector,
        contextual_bandit: ContextualBandit,
        min_pulls_for_context: int = 20,
    ):
        self.thompson = thompson_selector
        self.bandit = contextual_bandit
        self.min_pulls = min_pulls_for_context

    def select(
        self, context: Optional[ContextFeatures] = None
    ) -> Tuple[Any, str]:
        """
        选择动作。

        Returns:
            (action, method_used)
        """
        if context and self.bandit.total_pulls >= self.min_pulls * 5:
            action_id, score = self.bandit.select_action(context)
            return action_id, "contextual_bandit"
        else:
            action = self.thompson.select_action()
            return action, "thompson_sampling"

    def update(
        self,
        action: Any,
        reward: float,
        context: Optional[ContextFeatures] = None,
    ):
        """同时更新两个模型"""
        if isinstance(action, int) and context:
            self.bandit.update(action, context, reward)

        if hasattr(self.thompson, 'update'):
            self.thompson.update(action, reward)
