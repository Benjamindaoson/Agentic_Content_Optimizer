"""
混合奖励模型 V2 单元测试
Hybrid Reward Model V2 Unit Tests
"""

import pytest
import numpy as np
from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2, RewardBreakdown


@pytest.mark.unit
@pytest.mark.rl
class TestHybridRewardModelV2:
    """混合奖励模型 V2 测试"""

    @pytest.fixture
    def reward_model(self):
        """奖励模型实例"""
        return HybridRewardModelV2(
            reward_shaping=True,
            reward_scale=10.0
        )

    @pytest.fixture
    def sample_content(self):
        """示例内容"""
        return {
            "topic": "AI 写作",
            "text": "这是一篇关于 AI 写作的文章",
            "platform": "xiaohongshu"
        }

    @pytest.fixture
    def sample_context(self):
        """示例上下文"""
        return {
            "target_audience": "技术爱好者",
            "style": "professional"
        }

    @pytest.fixture
    def sample_action(self):
        """示例动作"""
        return {
            "hook": "你知道吗？",
            "body": "AI 写作正在改变内容创作",
            "cta": "关注我了解更多"
        }

    def test_initialization(self, reward_model):
        """测试初始化"""
        assert reward_model.reward_shaping is True
        assert reward_model.reward_scale == 10.0
        assert reward_model.weights is not None

    def test_calculate_reward_structure(self, reward_model, sample_content, sample_context, sample_action):
        """测试奖励计算结构"""
        critic_eval = {"score": 0.8, "feedback": "Good content"}

        reward = reward_model.calculate_reward(
            content=sample_content,
            context=sample_context,
            critic_eval=critic_eval,
            action=sample_action
        )

        # 验证返回类型
        assert isinstance(reward, RewardBreakdown)

        # 验证所有组件存在
        assert hasattr(reward, "total")
        assert hasattr(reward, "real_world")
        assert hasattr(reward, "quality")
        assert hasattr(reward, "system_health")

    def test_reward_range(self, reward_model, sample_content, sample_context, sample_action):
        """测试奖励范围"""
        # 高质量内容
        high_quality_eval = {"score": 0.95, "feedback": "Excellent"}
        high_reward = reward_model.calculate_reward(
            sample_content, sample_context, high_quality_eval, sample_action
        )

        # 低质量内容
        low_quality_eval = {"score": 0.2, "feedback": "Poor"}
        low_reward = reward_model.calculate_reward(
            sample_content, sample_context, low_quality_eval, sample_action
        )

        # 验证高质量内容的奖励更高
        assert high_reward.total > low_reward.total

    def test_reward_shaping(self, assert_almost_equal):
        """测试奖励塑形"""
        model_with_shaping = HybridRewardModelV2(reward_shaping=True, reward_scale=10.0)
        model_without_shaping = HybridRewardModelV2(reward_shaping=False, reward_scale=10.0)

        # 测试数据
        content = {"topic": "test", "text": "test content", "platform": "xiaohongshu"}
        context = {"style": "professional"}
        action = {"hook": "test", "body": "test", "cta": "test"}
        critic_eval = {"score": 0.8, "feedback": "Good"}

        reward_shaped = model_with_shaping.calculate_reward(content, context, critic_eval, action)
        reward_unshape = model_without_shaping.calculate_reward(content, context, critic_eval, action)

        # 验证奖励塑形放大了差异
        assert abs(reward_shaped.total) > abs(reward_unshape.total)

    def test_reward_components_weights(self, reward_model):
        """测试奖励组件权重"""
        # 验证权重总和为 1
        total_weight = sum(reward_model.weights.values())
        assert abs(total_weight - 1.0) < 1e-6

        # 验证所有权重为正
        assert all(w > 0 for w in reward_model.weights.values())

    def test_extreme_scores(self, reward_model, sample_content, sample_context, sample_action):
        """测试极端分数"""
        # 完美分数
        perfect_eval = {"score": 1.0, "feedback": "Perfect"}
        perfect_reward = reward_model.calculate_reward(
            sample_content, sample_context, perfect_eval, sample_action
        )

        # 最差分数
        worst_eval = {"score": 0.0, "feedback": "Terrible"}
        worst_reward = reward_model.calculate_reward(
            sample_content, sample_context, worst_eval, sample_action
        )

        # 验证奖励在合理范围内
        assert -50 < perfect_reward.total < 50
        assert -50 < worst_reward.total < 50

    def test_reward_breakdown_components(self, reward_model, sample_content, sample_context, sample_action):
        """测试奖励分解组件"""
        critic_eval = {"score": 0.8, "feedback": "Good"}

        reward = reward_model.calculate_reward(
            sample_content, sample_context, critic_eval, sample_action
        )

        # 验证所有组件都有贡献
        assert reward.real_world != 0
        assert reward.quality != 0
        assert reward.system_health != 0

        # 验证总奖励是组件的加权和
        weighted_sum = (
            reward_model.weights["real_world"] * reward.real_world +
            reward_model.weights["quality"] * reward.quality +
            reward_model.weights["system_health"] * reward.system_health
        )

        # 如果启用了奖励塑形，总奖励会不同
        if reward_model.reward_shaping:
            assert reward.total != weighted_sum
        else:
            assert abs(reward.total - weighted_sum) < 1e-6

    def test_consistency(self, reward_model, sample_content, sample_context, sample_action):
        """测试一致性"""
        critic_eval = {"score": 0.8, "feedback": "Good"}

        # 多次计算相同输入
        rewards = [
            reward_model.calculate_reward(sample_content, sample_context, critic_eval, sample_action)
            for _ in range(10)
        ]

        # 验证结果一致
        first_reward = rewards[0].total
        for reward in rewards[1:]:
            assert abs(reward.total - first_reward) < 1e-6
