"""
GRPO 引擎单元测试 - PyTorch 实现
GRPO Engine Unit Tests (PyTorch implementation)
"""

import pytest
import numpy as np
from app.ml.rl.grpo_engine import GRPOEngine, GRPOConfig


@pytest.mark.unit
@pytest.mark.rl
class TestGRPOEngine:
    """GRPO 引擎测试 - 适配当前 PyTorch 实现"""

    @pytest.fixture
    def grpo_engine(self):
        """GRPO 引擎实例"""
        return GRPOEngine(
            learning_rate=1e-4,
            temperature=1.0,
            clip_epsilon=0.2,
            state_dim=32,
            hidden_dim=64,
            action_dim=16,
        )

    def test_initialization(self, grpo_engine):
        """测试初始化"""
        assert grpo_engine.policy_net is not None
        assert grpo_engine.optimizer is not None
        assert grpo_engine.state_encoder is not None
        assert grpo_engine._action_to_idx == {}
        assert grpo_engine._idx_to_action == {}

    def test_action_to_key(self, grpo_engine):
        """测试动作键唯一性"""
        action1 = {"hook": "H01", "body": "B02", "cta": "C03"}
        action2 = {"hook": "H01", "body": "B23", "cta": "C01"}

        key1 = grpo_engine._action_to_key(action1)
        key2 = grpo_engine._action_to_key(action2)

        assert key1 != key2
        assert isinstance(key1, str)
        assert isinstance(key2, str)

    def test_sample_action_exploration(self, grpo_engine):
        """测试探索模式下的动作采样（空策略时随机采样）"""
        action_space = [
            {"hook": "H01", "body": "B01", "cta": "C01"},
            {"hook": "H02", "body": "B02", "cta": "C02"},
        ]

        samples = [
            grpo_engine.sample_action(action_space, exploration=True)
            for _ in range(20)
        ]

        for s in samples:
            assert s in action_space

    def test_sample_action_with_policy(self, grpo_engine):
        """测试策略模式下的动作采样"""
        action_space = [
            {"hook": "H01", "body": "B01", "cta": "C01"},
            {"hook": "H02", "body": "B02", "cta": "C02"},
        ]

        # 先通过 update_policy 注册动作
        from app.schemas.policy import Experience, Episode

        experiences = [
            Experience(
                topic="test",
                platform="xiaohongshu",
                goal_metric="engagement",
                geo_keywords=[],
                action=action_space[i % 2],
                reward=0.5 + (i % 2) * 0.3,
                generated_content={},
                evaluation={},
                episode_id="ep1",
            )
            for i in range(4)
        ]

        episode = Episode(
            episode_id="ep1",
            topic="test",
            platform="xiaohongshu",
            goal_metric="engagement",
            experiences=experiences,
            total_experiences=4,
            approved_count=2,
            avg_reward=0.6,
            max_reward=0.9,
            min_reward=0.4,
        )

        grpo_engine.update_policy(episode)

        # 现在可以按策略采样
        samples = [
            grpo_engine.sample_action(action_space, exploration=False)
            for _ in range(20)
        ]
        for s in samples:
            assert s in action_space

    def test_get_top_actions(self, grpo_engine):
        """测试获取 top-k 动作"""
        action_space = [
            {"hook": f"H0{i}", "body": f"B0{i}", "cta": "C01"}
            for i in range(1, 6)
        ]

        top = grpo_engine.get_top_actions(action_space, k=3)
        assert len(top) == 3
        for a in top:
            assert a in action_space

    def test_relative_rewards_calculation(self, grpo_engine):
        """测试相对奖励计算"""
        from app.schemas.policy import Experience, Episode

        experiences = [
            Experience(
                topic="t",
                platform="xhs",
                goal_metric="eng",
                geo_keywords=[],
                action={"hook": "H01", "body": "B01", "cta": "C01"},
                reward=1.0,
                generated_content={},
                evaluation={},
                episode_id="ep1",
            ),
            Experience(
                topic="t",
                platform="xhs",
                goal_metric="eng",
                geo_keywords=[],
                action={"hook": "H02", "body": "B02", "cta": "C02"},
                reward=0.2,
                generated_content={},
                evaluation={},
                episode_id="ep1",
            ),
        ]

        episode = Episode(
            episode_id="ep1",
            topic="t",
            platform="xhs",
            goal_metric="eng",
            experiences=experiences,
            total_experiences=2,
            approved_count=1,
            avg_reward=0.6,
            max_reward=1.0,
            min_reward=0.2,
        )

        update = grpo_engine.update_policy(episode)
        assert update.episode_id == "ep1"
        assert len(update.relative_rewards) == 2
        assert abs(np.mean(update.relative_rewards)) < 0.01  # 均值接近 0

    def test_grpo_config_dataclass(self):
        """测试 GRPOConfig 向后兼容"""
        config = GRPOConfig(
            group_size=4,
            epsilon=0.1,
            learning_rate=1e-4,
            entropy_coef=0.01,
        )
        assert config.group_size == 4
        assert config.epsilon == 0.1
