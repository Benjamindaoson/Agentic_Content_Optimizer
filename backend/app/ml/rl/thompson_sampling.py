"""
Thompson Sampling 策略选择器

用于 400 种离散动作空间的高效探索和利用

核心功能:
1. Thompson Sampling（贝叶斯 Bandit）
2. 层级采样（Hook → Body → CTA）
3. 近邻泛化（相似策略共享经验）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Callable
import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class BanditArm:
    """Bandit 臂统计"""
    n_pulls: int = 0  # 尝试次数
    sum_reward: float = 0.0  # 累计奖励
    sum_reward_sq: float = 0.0  # 累计奖励平方（用于计算方差）

    @property
    def mean(self) -> float:
        """均值奖励"""
        return self.sum_reward / self.n_pulls if self.n_pulls > 0 else 0.0

    @property
    def variance(self) -> float:
        """奖励方差"""
        if self.n_pulls < 2:
            return 1.0  # 初始方差设为 1
        mean_sq = (self.sum_reward / self.n_pulls) ** 2
        return max(self.sum_reward_sq / self.n_pulls - mean_sq, 1e-6)

    @property
    def std(self) -> float:
        """标准差"""
        return np.sqrt(self.variance)

    def update(self, reward: float):
        """更新统计"""
        self.n_pulls += 1
        self.sum_reward += reward
        self.sum_reward_sq += reward ** 2


@dataclass
class ThompsonSamplingConfig:
    """Thompson Sampling 配置"""

    # 初始先验参数（Beta 分布）
    prior_alpha: float = 1.0
    prior_beta: float = 1.0

    # 探索强度（温度参数）
    temperature: float = 1.0

    # 最小尝试次数（每个臂至少尝试多少次）
    min_pulls: int = 3

    # 是否使用层级采样
    use_hierarchical: bool = True

    # 是否使用近邻泛化
    use_neighbor_sharing: bool = False

    # 近邻数量
    n_neighbors: int = 5


class ThompsonSamplingSelector:
    """
    Thompson Sampling 策略选择器

    支持:
    1. 标准 Thompson Sampling
    2. 层级采样（Hook → Body → CTA）
    3. 近邻泛化（可选）
    """

    def __init__(
        self,
        n_hooks: int,
        n_bodies: int,
        n_ctas: int,
        config: Optional[ThompsonSamplingConfig] = None,
        embed_fn: Optional[Callable[[str], np.ndarray]] = None
    ):
        """
        初始化

        Args:
            n_hooks: Hook 数量
            n_bodies: Body 数量
            n_ctas: CTA 数量
            config: 配置
            embed_fn: Embedding 函数（用于近邻泛化）
        """
        self.n_hooks = n_hooks
        self.n_bodies = n_bodies
        self.n_ctas = n_ctas
        self.config = config or ThompsonSamplingConfig()
        self.embed_fn = embed_fn

        # 策略统计（triplet 级别）
        self.triplet_stats: Dict[Tuple[int, int, int], BanditArm] = defaultdict(BanditArm)

        # 层级统计（用于层级采样）
        self.hook_stats: Dict[int, BanditArm] = defaultdict(BanditArm)
        self.body_given_hook_stats: Dict[Tuple[int, int], BanditArm] = defaultdict(BanditArm)
        self.cta_given_hook_body_stats: Dict[Tuple[int, int, int], BanditArm] = defaultdict(BanditArm)

        # 近邻泛化（可选）
        self.hook_embeds: Optional[np.ndarray] = None
        self.body_embeds: Optional[np.ndarray] = None
        self.cta_embeds: Optional[np.ndarray] = None

        logger.info(f"✅ ThompsonSamplingSelector 初始化完成 "
                   f"({n_hooks}x{n_bodies}x{n_ctas}={n_hooks*n_bodies*n_ctas} 动作)")

    def select_action(self, mode: str = "auto") -> Tuple[int, int, int]:
        """
        选择动作

        Args:
            mode: 选择模式
                - "auto": 自动选择（根据配置）
                - "hierarchical": 层级采样
                - "flat": 扁平采样
                - "random": 随机采样（baseline）

        Returns:
            (hook_id, body_id, cta_id)
        """
        if mode == "random":
            return self._select_random()

        if mode == "hierarchical" or (mode == "auto" and self.config.use_hierarchical):
            return self._select_hierarchical()

        return self._select_flat()

    def _select_random(self) -> Tuple[int, int, int]:
        """随机采样（baseline）"""
        hook_id = np.random.randint(0, self.n_hooks)
        body_id = np.random.randint(0, self.n_bodies)
        cta_id = np.random.randint(0, self.n_ctas)
        return (hook_id, body_id, cta_id)

    def _select_flat(self) -> Tuple[int, int, int]:
        """扁平 Thompson Sampling（直接在 triplet 空间采样）"""

        # 1. 找出所有可能的 triplet
        all_triplets = [
            (h, b, c)
            for h in range(self.n_hooks)
            for b in range(self.n_bodies)
            for c in range(self.n_ctas)
        ]

        # 2. 对每个 triplet 采样奖励
        sampled_rewards = []
        for triplet in all_triplets:
            arm = self.triplet_stats[triplet]

            # 如果尝试次数不足，优先选择
            if arm.n_pulls < self.config.min_pulls:
                sampled_reward = 1.0  # 高优先级
            else:
                # Thompson Sampling: 从后验分布采样
                sampled_reward = self._sample_from_posterior(arm)

            sampled_rewards.append(sampled_reward)

        # 3. 选择采样奖励最高的
        best_idx = np.argmax(sampled_rewards)
        return all_triplets[best_idx]

    def _select_hierarchical(self) -> Tuple[int, int, int]:
        """层级 Thompson Sampling（Hook → Body → CTA）"""

        # 1. 选择 Hook
        hook_id = self._select_from_arms(
            list(range(self.n_hooks)),
            lambda h: self.hook_stats[h]
        )

        # 2. 选择 Body（给定 Hook）
        body_id = self._select_from_arms(
            list(range(self.n_bodies)),
            lambda b: self.body_given_hook_stats[(hook_id, b)]
        )

        # 3. 选择 CTA（给定 Hook 和 Body）
        cta_id = self._select_from_arms(
            list(range(self.n_ctas)),
            lambda c: self.cta_given_hook_body_stats[(hook_id, body_id, c)]
        )

        return (hook_id, body_id, cta_id)

    def _select_from_arms(
        self,
        arm_ids: List[int],
        get_arm: Callable[[int], BanditArm]
    ) -> int:
        """从一组臂中选择"""

        sampled_rewards = []
        for arm_id in arm_ids:
            arm = get_arm(arm_id)

            # 优先选择尝试次数不足的
            if arm.n_pulls < self.config.min_pulls:
                sampled_reward = 1.0
            else:
                sampled_reward = self._sample_from_posterior(arm)

            sampled_rewards.append(sampled_reward)

        # 选择采样奖励最高的
        best_idx = np.argmax(sampled_rewards)
        return arm_ids[best_idx]

    def _sample_from_posterior(self, arm: BanditArm) -> float:
        """从后验分布采样"""

        if arm.n_pulls == 0:
            # 使用先验
            mean = 0.5
            std = 0.5
        else:
            mean = arm.mean
            std = arm.std

        # 加入温度参数
        std = std * self.config.temperature

        # 从正态分布采样
        sampled = np.random.normal(mean, std)

        return float(sampled)

    def update(self, action: Tuple[int, int, int], reward: float):
        """
        更新统计

        Args:
            action: (hook_id, body_id, cta_id)
            reward: 奖励值
        """
        hook_id, body_id, cta_id = action

        # 更新 triplet 统计
        self.triplet_stats[action].update(reward)

        # 更新层级统计
        self.hook_stats[hook_id].update(reward)
        self.body_given_hook_stats[(hook_id, body_id)].update(reward)
        self.cta_given_hook_body_stats[(hook_id, body_id, cta_id)].update(reward)

    def get_best_action(self) -> Tuple[int, int, int]:
        """获取当前最佳动作（纯利用，不探索）"""

        if self.config.use_hierarchical:
            # 层级选择最佳
            hook_id = max(
                range(self.n_hooks),
                key=lambda h: self.hook_stats[h].mean if self.hook_stats[h].n_pulls > 0 else 0
            )

            body_id = max(
                range(self.n_bodies),
                key=lambda b: self.body_given_hook_stats[(hook_id, b)].mean
                if self.body_given_hook_stats[(hook_id, b)].n_pulls > 0 else 0
            )

            cta_id = max(
                range(self.n_ctas),
                key=lambda c: self.cta_given_hook_body_stats[(hook_id, body_id, c)].mean
                if self.cta_given_hook_body_stats[(hook_id, body_id, c)].n_pulls > 0 else 0
            )

            return (hook_id, body_id, cta_id)

        else:
            # 扁平选择最佳
            if not self.triplet_stats:
                return self._select_random()

            best_triplet = max(
                self.triplet_stats.items(),
                key=lambda x: x[1].mean if x[1].n_pulls > 0 else 0
            )[0]

            return best_triplet

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""

        # Top 10 triplets
        top_triplets = sorted(
            [(k, v.mean, v.n_pulls) for k, v in self.triplet_stats.items() if v.n_pulls > 0],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Hook 统计
        hook_stats = {
            h: {'mean': self.hook_stats[h].mean, 'n_pulls': self.hook_stats[h].n_pulls}
            for h in range(self.n_hooks)
            if self.hook_stats[h].n_pulls > 0
        }

        # 探索率
        total_pulls = sum(arm.n_pulls for arm in self.triplet_stats.values())
        explored_triplets = sum(1 for arm in self.triplet_stats.values() if arm.n_pulls > 0)
        total_triplets = self.n_hooks * self.n_bodies * self.n_ctas

        return {
            'total_pulls': total_pulls,
            'explored_triplets': explored_triplets,
            'total_triplets': total_triplets,
            'exploration_rate': explored_triplets / total_triplets if total_triplets > 0 else 0,
            'top_triplets': top_triplets,
            'hook_stats': hook_stats,
            'best_action': self.get_best_action()
        }

    def set_embeddings(
        self,
        hook_embeds: Optional[np.ndarray] = None,
        body_embeds: Optional[np.ndarray] = None,
        cta_embeds: Optional[np.ndarray] = None
    ):
        """
        设置 embeddings（用于近邻泛化）

        Args:
            hook_embeds: Hook embeddings [n_hooks, d]
            body_embeds: Body embeddings [n_bodies, d]
            cta_embeds: CTA embeddings [n_ctas, d]
        """
        self.hook_embeds = hook_embeds
        self.body_embeds = body_embeds
        self.cta_embeds = cta_embeds

        if hook_embeds is not None:
            logger.info(f"✅ 设置 Hook embeddings: {hook_embeds.shape}")
        if body_embeds is not None:
            logger.info(f"✅ 设置 Body embeddings: {body_embeds.shape}")
        if cta_embeds is not None:
            logger.info(f"✅ 设置 CTA embeddings: {cta_embeds.shape}")

    def get_neighbor_prior(self, action: Tuple[int, int, int]) -> Tuple[float, float]:
        """
        获取近邻先验（用于冷启动）

        Args:
            action: (hook_id, body_id, cta_id)

        Returns:
            (prior_mean, prior_std)
        """
        if not self.config.use_neighbor_sharing:
            return (0.5, 0.5)

        hook_id, body_id, cta_id = action

        # 如果没有 embeddings，返回默认先验
        if self.hook_embeds is None or self.body_embeds is None or self.cta_embeds is None:
            return (0.5, 0.5)

        # 找近邻并计算加权平均
        neighbor_rewards = []

        # 简化版本：只看 triplet 近邻
        # 实际可以分别看 hook/body/cta 近邻

        for triplet, arm in self.triplet_stats.items():
            if arm.n_pulls == 0:
                continue

            # 计算相似度（简单版本：欧氏距离）
            h, b, c = triplet
            dist = (
                np.linalg.norm(self.hook_embeds[hook_id] - self.hook_embeds[h]) +
                np.linalg.norm(self.body_embeds[body_id] - self.body_embeds[b]) +
                np.linalg.norm(self.cta_embeds[cta_id] - self.cta_embeds[c])
            )

            neighbor_rewards.append((dist, arm.mean))

        if not neighbor_rewards:
            return (0.5, 0.5)

        # 取最近的 k 个
        neighbor_rewards.sort(key=lambda x: x[0])
        top_k = neighbor_rewards[:self.config.n_neighbors]

        # 加权平均（距离越近权重越大）
        weights = [1.0 / (d + 1e-6) for d, _ in top_k]
        weights = np.array(weights) / sum(weights)
        rewards = [r for _, r in top_k]

        prior_mean = float(np.dot(weights, rewards))
        prior_std = float(np.std(rewards)) if len(rewards) > 1 else 0.5

        return (prior_mean, prior_std)
