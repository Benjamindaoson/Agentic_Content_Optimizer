"""
多样性感知经验池 - 防止自我强化和模式化
Diversity-Aware Experience Pool
"""

from typing import List, Dict, Any, Optional
import logging
import random
import numpy as np
from datetime import datetime
from collections import defaultdict

from app.schemas.policy import Experience, Episode

logger = logging.getLogger(__name__)


class DiversityAwareExperiencePool:
    """
    多样性感知的经验池

    功能：
    1. 追踪动作分布和新颖度
    2. 多样性感知采样（平衡质量和探索）
    3. 防止自我强化
    4. 支持多种采样策略
    """

    def __init__(
        self,
        max_size: int = 1000,
        max_episodes: int = 100,
        novelty_decay: float = 0.95  # 新颖度衰减系数
    ):
        """
        初始化多样性感知经验池

        Args:
            max_size: 最大经验数量
            max_episodes: 最大 episode 数量
            novelty_decay: 新颖度衰减系数
        """
        self.max_size = max_size
        self.max_episodes = max_episodes
        self.novelty_decay = novelty_decay

        # 存储
        self.episodes: List[Episode] = []
        self.experiences: List[Experience] = []

        # 索引
        self.episode_index: Dict[str, Episode] = {}
        self.action_index: Dict[str, List[Experience]] = {}

        # 多样性追踪
        self.action_distribution: Dict[str, int] = defaultdict(int)
        self.novelty_scores: Dict[str, float] = {}
        self.action_embeddings: Dict[str, List[float]] = {}  # 简化版：用特征向量

        # 统计
        self.total_added = 0
        self.total_sampled = 0

        logger.info(
            f"Diversity-Aware Experience Pool initialized: "
            f"max_size={max_size}, max_episodes={max_episodes}, "
            f"novelty_decay={novelty_decay}"
        )

    def add_episode(self, episode: Episode):
        """添加一个 episode"""

        # 添加到列表
        self.episodes.append(episode)
        self.episode_index[episode.episode_id] = episode

        # 添加所有经验
        for exp in episode.experiences:
            self.add_experience(exp)

        # 检查容量
        self._check_capacity()

        logger.info(
            f"Episode added: {episode.episode_id}, "
            f"experiences={len(episode.experiences)}, "
            f"total_episodes={len(self.episodes)}"
        )

    def add_experience(self, experience: Experience):
        """添加单条经验 + 计算新颖度"""

        # 添加到列表
        self.experiences.append(experience)
        self.total_added += 1

        # 添加到动作索引
        action_key = self._action_to_key(experience.action)
        if action_key not in self.action_index:
            self.action_index[action_key] = []
        self.action_index[action_key].append(experience)

        # 更新动作分布
        self.action_distribution[action_key] += 1

        # 计算新颖度
        novelty = self._calculate_novelty(experience)
        self.novelty_scores[experience.experience_id] = novelty

        # 计算动作 embedding（简化版）
        self.action_embeddings[experience.experience_id] = self._compute_action_embedding(
            experience.action
        )

        logger.debug(
            f"Experience added: {experience.experience_id}, "
            f"action={action_key}, novelty={novelty:.3f}"
        )

    def sample_experiences(
        self,
        n: int,
        strategy: str = 'balanced',  # 'random', 'best', 'balanced', 'diverse', 'epsilon_greedy'
        filter_approved: bool = False,
        epsilon: float = 0.2  # for epsilon_greedy
    ) -> List[Experience]:
        """
        多样性感知采样

        Args:
            n: 采样数量
            strategy: 采样策略
                - random: 随机采样
                - best: 只采样高奖励的
                - diverse: 优先采样新颖的
                - balanced: 平衡质量和多样性（50/50）
                - epsilon_greedy: ε-贪心（ε 概率探索，1-ε 概率利用）
            filter_approved: 是否只采样通过的经验
            epsilon: epsilon_greedy 策略的探索率

        Returns:
            采样的经验列表
        """

        # 过滤
        if filter_approved:
            pool = [exp for exp in self.experiences if exp.approved]
        else:
            pool = self.experiences

        if not pool:
            logger.warning("Experience pool is empty")
            return []

        n = min(n, len(pool))
        self.total_sampled += n

        # 根据策略采样
        if strategy == 'random':
            sampled = random.sample(pool, n)

        elif strategy == 'best':
            # 只采样高奖励的
            sorted_pool = sorted(pool, key=lambda x: x.reward, reverse=True)
            sampled = sorted_pool[:n]

        elif strategy == 'diverse':
            # 优先采样新颖的
            sorted_pool = sorted(
                pool,
                key=lambda x: self.novelty_scores.get(x.experience_id, 0),
                reverse=True
            )
            sampled = sorted_pool[:n]

        elif strategy == 'balanced':
            # 平衡质量和多样性
            n_best = n // 2
            n_diverse = n - n_best

            # 高奖励的
            best = sorted(pool, key=lambda x: x.reward, reverse=True)[:n_best]

            # 高新颖度的（排除已选的）
            remaining = [e for e in pool if e not in best]
            diverse = sorted(
                remaining,
                key=lambda x: self.novelty_scores.get(x.experience_id, 0),
                reverse=True
            )[:n_diverse]

            sampled = best + diverse

        elif strategy == 'epsilon_greedy':
            # ε-贪心
            if random.random() < epsilon:
                # 探索：采样新颖的
                sorted_pool = sorted(
                    pool,
                    key=lambda x: self.novelty_scores.get(x.experience_id, 0),
                    reverse=True
                )
                sampled = sorted_pool[:n]
            else:
                # 利用：采样高奖励的
                sorted_pool = sorted(pool, key=lambda x: x.reward, reverse=True)
                sampled = sorted_pool[:n]

        else:
            logger.warning(f"Unknown strategy: {strategy}, using random")
            sampled = random.sample(pool, n)

        logger.info(
            f"Sampled {len(sampled)} experiences using strategy '{strategy}' "
            f"(total_sampled={self.total_sampled})"
        )

        return sampled

    def get_diversity_stats(self) -> Dict[str, Any]:
        """获取多样性统计"""

        if not self.experiences:
            return {}

        # 动作分布熵（衡量多样性）
        total = sum(self.action_distribution.values())
        probs = [count / total for count in self.action_distribution.values()]
        entropy = -sum(p * np.log(p) for p in probs if p > 0)

        # 平均新颖度
        avg_novelty = np.mean(list(self.novelty_scores.values())) if self.novelty_scores else 0

        # 最常见的动作
        top_actions = sorted(
            self.action_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'total_experiences': len(self.experiences),
            'unique_actions': len(self.action_distribution),
            'action_entropy': round(entropy, 3),
            'avg_novelty': round(avg_novelty, 3),
            'top_actions': [
                {'action': action, 'count': count, 'percentage': round(count / total * 100, 1)}
                for action, count in top_actions
            ],
            'sampling_stats': {
                'total_added': self.total_added,
                'total_sampled': self.total_sampled
            }
        }

    def _calculate_novelty(self, experience: Experience) -> float:
        """
        计算新颖度

        新颖度 = 1 / (1 + action_count) * decay^time

        越少见的动作，新颖度越高
        随时间衰减
        """

        action_key = self._action_to_key(experience.action)

        # 1. 基于频率的新颖度
        count = self.action_distribution.get(action_key, 0)
        frequency_novelty = 1.0 / (1.0 + count)

        # 2. 基于相似度的新颖度（与历史经验的差异）
        if self.action_embeddings:
            current_embedding = self._compute_action_embedding(experience.action)
            similarities = []

            for exp_id, hist_embedding in list(self.action_embeddings.items())[-50:]:  # 只比较最近50个
                similarity = self._cosine_similarity(current_embedding, hist_embedding)
                similarities.append(similarity)

            avg_similarity = np.mean(similarities) if similarities else 0
            similarity_novelty = 1.0 - avg_similarity
        else:
            similarity_novelty = 1.0

        # 3. 综合新颖度
        novelty = 0.6 * frequency_novelty + 0.4 * similarity_novelty

        # 4. 时间衰减（可选）
        # 这里简化，不考虑时间衰减

        return np.clip(novelty, 0, 1)

    def _compute_action_embedding(self, action: Dict[str, str]) -> List[float]:
        """
        计算动作的 embedding using StateEncoder for richer representation.
        """
        try:
            from app.ml.rl.networks import StateEncoder
            encoder = StateEncoder(state_dim=16)
            tensor = encoder.encode_action(action)
            return tensor.tolist()
        except Exception:
            # Fallback to simple encoding
            hook_id = int(action.get('hook', 'H0')[1:]) if action.get('hook', '').startswith('H') else 0
            body_id = int(action.get('body', 'B0')[1:]) if action.get('body', '').startswith('B') else 0
            cta_id = int(action.get('cta', 'C0')[1:]) if action.get('cta', '').startswith('C') else 0
            return [hook_id / 10.0, body_id / 8.0, cta_id / 5.0]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0

        return dot_product / (norm1 * norm2)

    def _action_to_key(self, action: Dict[str, str]) -> str:
        """将动作转换为字符串键"""
        return f"{action['hook']}_{action['body']}_{action['cta']}"

    def _check_capacity(self):
        """检查容量并清理"""

        # 清理 episodes
        if len(self.episodes) > self.max_episodes:
            # 移除最旧的 episode
            removed_episode = self.episodes.pop(0)
            del self.episode_index[removed_episode.episode_id]

            logger.info(f"Removed oldest episode: {removed_episode.episode_id}")

        # 清理 experiences
        if len(self.experiences) > self.max_size:
            # 移除最旧的经验
            removed_count = len(self.experiences) - self.max_size
            removed_experiences = self.experiences[:removed_count]
            self.experiences = self.experiences[removed_count:]

            # 更新索引
            for exp in removed_experiences:
                action_key = self._action_to_key(exp.action)
                if action_key in self.action_index:
                    self.action_index[action_key] = [
                        e for e in self.action_index[action_key]
                        if e.experience_id != exp.experience_id
                    ]

                # 更新分布
                if action_key in self.action_distribution:
                    self.action_distribution[action_key] -= 1
                    if self.action_distribution[action_key] <= 0:
                        del self.action_distribution[action_key]

                # 删除新颖度和 embedding
                if exp.experience_id in self.novelty_scores:
                    del self.novelty_scores[exp.experience_id]
                if exp.experience_id in self.action_embeddings:
                    del self.action_embeddings[exp.experience_id]

            logger.info(f"Removed {removed_count} oldest experiences")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""

        if not self.experiences:
            return {
                'total_episodes': 0,
                'total_experiences': 0,
                'avg_reward': 0,
                'diversity_stats': {}
            }

        rewards = [exp.reward for exp in self.experiences]
        approved_count = sum(1 for exp in self.experiences if exp.approved)

        return {
            'total_episodes': len(self.episodes),
            'total_experiences': len(self.experiences),
            'avg_reward': round(np.mean(rewards), 3),
            'max_reward': round(max(rewards), 3),
            'min_reward': round(min(rewards), 3),
            'approval_rate': round(approved_count / len(self.experiences), 3),
            'diversity_stats': self.get_diversity_stats()
        }

    def get_recent_episodes(self, n: int = 10) -> List[Episode]:
        """获取最近的 episodes"""
        return self.episodes[-n:]

    def clear(self):
        """清空经验池"""
        self.episodes.clear()
        self.experiences.clear()
        self.episode_index.clear()
        self.action_index.clear()
        self.action_distribution.clear()
        self.novelty_scores.clear()
        self.action_embeddings.clear()
        self.total_added = 0
        self.total_sampled = 0

        logger.info("Experience pool cleared")
