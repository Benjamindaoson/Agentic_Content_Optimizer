from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import json

from app.schemas.policy import Experience, Episode

logger = logging.getLogger(__name__)


class ExperiencePool:
    """
    经验池 - 存储和管理历史经验

    功能：
    1. 存储 episode 和 experience
    2. 采样经验用于训练
    3. 统计分析
    4. 持久化

    升级版：支持多样性感知经验池（可选）
    """

    def __init__(
        self,
        max_size: int = 1000,
        max_episodes: int = 100,
        use_diversity_aware: bool = False,
        diversity_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化经验池

        Args:
            max_size: 最大经验数量
            max_episodes: 最大 episode 数量
            use_diversity_aware: 是否使用多样性感知经验池
            diversity_config: 多样性配置
        """
        self.max_size = max_size
        self.max_episodes = max_episodes
        self.use_diversity_aware = use_diversity_aware

        # 如果启用多样性感知，使用增强版
        if use_diversity_aware:
            try:
                from app.ml.rl.diversity_experience_pool import DiversityAwareExperiencePool

                diversity_config = diversity_config or {}
                self._pool = DiversityAwareExperiencePool(
                    max_size=max_size,
                    max_episodes=max_episodes,
                    novelty_decay=diversity_config.get('novelty_decay', 0.95)
                )
                logger.info("Diversity-Aware Experience Pool enabled")
            except ImportError:
                logger.warning("Diversity-Aware Experience Pool not available, using standard pool")
                self.use_diversity_aware = False
                self._init_standard_pool()
        else:
            self._init_standard_pool()

    def _init_standard_pool(self):
        """初始化标准经验池"""
        # 存储
        self.episodes: List[Episode] = []
        self.experiences: List[Experience] = []

        # 索引
        self.episode_index: Dict[str, Episode] = {}
        self.action_index: Dict[str, List[Experience]] = {}

        logger.info(
            f"Experience Pool initialized: max_size={self.max_size}, "
            f"max_episodes={self.max_episodes}"
        )

    def add_episode(self, episode: Episode):
        """添加一个 episode"""

        # 如果使用多样性感知池，代理到增强版
        if self.use_diversity_aware:
            return self._pool.add_episode(episode)

        # 标准实现
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
        """添加单条经验"""

        # 如果使用多样性感知池，代理到增强版
        if self.use_diversity_aware:
            return self._pool.add_experience(experience)

        # 标准实现
        # 添加到列表
        self.experiences.append(experience)

        # 添加到动作索引
        action_key = self._action_to_key(experience.action)
        if action_key not in self.action_index:
            self.action_index[action_key] = []
        self.action_index[action_key].append(experience)

    def sample_experiences(
        self,
        n: int,
        filter_approved: bool = False,
        strategy: str = 'random'  # 新增：采样策略
    ) -> List[Experience]:
        """
        采样经验

        Args:
            n: 采样数量
            filter_approved: 是否只采样通过的经验
            strategy: 采样策略（仅多样性感知池支持）
                - random: 随机采样
                - best: 只采样高奖励的
                - balanced: 平衡质量和多样性
                - diverse: 优先采样新颖的
                - epsilon_greedy: ε-贪心

        Returns:
            采样的经验列表
        """

        # 如果使用多样性感知池，代理到增强版
        if self.use_diversity_aware:
            return self._pool.sample_experiences(
                n=n,
                strategy=strategy,
                filter_approved=filter_approved
            )

        # 标准实现（随机采样）
        if filter_approved:
            pool = [exp for exp in self.experiences if exp.approved]
        else:
            pool = self.experiences

        if len(pool) == 0:
            return []

        # 随机采样
        import random
        n = min(n, len(pool))
        return random.sample(pool, n)

    def get_experiences_by_action(
        self,
        action: Dict[str, str]
    ) -> List[Experience]:
        """获取特定动作的所有经验"""

        action_key = self._action_to_key(action)
        return self.action_index.get(action_key, [])

    def get_recent_episodes(self, n: int = 10) -> List[Episode]:
        """获取最近的 n 个 episode"""
        if self.use_diversity_aware:
            return self._pool.get_recent_episodes(n)
        return self.episodes[-n:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""

        # 如果使用多样性感知池，代理到增强版
        if self.use_diversity_aware:
            return self._pool.get_statistics()

        # 标准实现
        if len(self.experiences) == 0:
            return {
                "total_episodes": 0,
                "total_experiences": 0,
                "approved_count": 0,
                "approval_rate": 0.0,
                "avg_reward": 0.0,
                "max_reward": 0.0,
                "min_reward": 0.0
            }

        approved_count = sum(1 for exp in self.experiences if exp.approved)
        rewards = [exp.reward for exp in self.experiences]

        return {
            "total_episodes": len(self.episodes),
            "total_experiences": len(self.experiences),
            "approved_count": approved_count,
            "approval_rate": approved_count / len(self.experiences),
            "avg_reward": sum(rewards) / len(rewards),
            "max_reward": max(rewards),
            "min_reward": min(rewards),
            "unique_actions": len(self.action_index),
            "pool_utilization": len(self.experiences) / self.max_size
        }

    def get_action_statistics(self) -> Dict[str, Dict[str, Any]]:
        """获取每个动作的统计信息"""

        action_stats = {}

        for action_key, experiences in self.action_index.items():
            rewards = [exp.reward for exp in experiences]
            approved_count = sum(1 for exp in experiences if exp.approved)

            action_stats[action_key] = {
                "count": len(experiences),
                "approved_count": approved_count,
                "approval_rate": approved_count / len(experiences) if experiences else 0,
                "avg_reward": sum(rewards) / len(rewards) if rewards else 0,
                "max_reward": max(rewards) if rewards else 0,
                "min_reward": min(rewards) if rewards else 0
            }

        return action_stats

    def get_best_actions(self, k: int = 10) -> List[Dict[str, Any]]:
        """获取表现最好的 k 个动作"""

        action_stats = self.get_action_statistics()

        # 按平均奖励排序
        sorted_actions = sorted(
            action_stats.items(),
            key=lambda x: x[1]["avg_reward"],
            reverse=True
        )

        # 返回 top-k
        return [
            {
                "action": self._key_to_action(action_key),
                "stats": stats
            }
            for action_key, stats in sorted_actions[:k]
        ]

    def _check_capacity(self):
        """检查容量并清理旧数据"""

        # 清理旧 episode
        if len(self.episodes) > self.max_episodes:
            removed_episodes = self.episodes[:len(self.episodes) - self.max_episodes]
            self.episodes = self.episodes[-self.max_episodes:]

            # 从索引中移除
            for episode in removed_episodes:
                if episode.episode_id in self.episode_index:
                    del self.episode_index[episode.episode_id]

            logger.info(f"Removed {len(removed_episodes)} old episodes")

        # 清理旧经验
        if len(self.experiences) > self.max_size:
            removed_count = len(self.experiences) - self.max_size
            removed_experiences = self.experiences[:removed_count]
            self.experiences = self.experiences[-self.max_size:]

            # 重建动作索引
            self._rebuild_action_index()

            logger.info(f"Removed {removed_count} old experiences")

    def _rebuild_action_index(self):
        """重建动作索引"""

        self.action_index = {}
        for exp in self.experiences:
            action_key = self._action_to_key(exp.action)
            if action_key not in self.action_index:
                self.action_index[action_key] = []
            self.action_index[action_key].append(exp)

    def _action_to_key(self, action: Dict[str, str]) -> str:
        """将动作转换为字符串键"""
        return f"{action['hook']}_{action['body']}_{action['cta']}"

    def _key_to_action(self, key: str) -> Dict[str, str]:
        """将字符串键转换为动作"""
        parts = key.split('_')
        return {
            "hook": parts[0],
            "body": parts[1],
            "cta": parts[2]
        }

    def save_to_file(self, filepath: str):
        """保存经验池到文件"""

        data = {
            "episodes": [ep.dict() for ep in self.episodes],
            "statistics": self.get_statistics(),
            "saved_at": datetime.now().isoformat()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Experience pool saved to {filepath}")

    def load_from_file(self, filepath: str):
        """从文件加载经验池"""

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 清空当前数据
        self.episodes = []
        self.experiences = []
        self.episode_index = {}
        self.action_index = {}

        # 加载 episodes
        for ep_data in data["episodes"]:
            episode = Episode(**ep_data)
            self.add_episode(episode)

        logger.info(
            f"Experience pool loaded from {filepath}: "
            f"{len(self.episodes)} episodes, {len(self.experiences)} experiences"
        )

    def clear(self):
        """清空经验池"""
        self.episodes = []
        self.experiences = []
        self.episode_index = {}
        self.action_index = {}
        logger.info("Experience pool cleared")
