"""
混合奖励模型 V2 单元测试
Hybrid Reward Model V2 Unit Tests
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
@pytest.mark.rl
class TestHybridRewardModelV2:
    """混合奖励模型 V2 测试"""

    @pytest.fixture
    def mock_predictor(self):
        """Mock RealMetricPredictorEnsemble"""
        predictor = MagicMock()
        predictor.predict.return_value = {
            "ctr": 0.05,
            "completion_rate": 0.6,
            "engagement_rate": 0.15,
            "conversion_rate": 0.02,
        }
        return predictor

    def test_reward_breakdown_structure(self):
        """测试 RewardBreakdown 数据结构"""
        from app.ml.rl.hybrid_reward_model_v2 import RewardBreakdown

        breakdown = RewardBreakdown(
            total_reward=0.75,
            real_world_reward=0.5,
            quality_reward=0.2,
            system_health_reward=0.05,
            real_metrics={"ctr": 0.05, "engagement": 0.15},
            quality_components={"critic": 0.8, "structure": 0.9},
            health_components={"diversity": 0.7, "novelty": 0.6},
        )
        assert breakdown.total_reward == 0.75
        assert breakdown.real_world_reward == 0.5
        assert "ctr" in breakdown.real_metrics

    @patch("app.ml.rl.hybrid_reward_model_v2.RealMetricPredictorEnsemble")
    def test_hybrid_reward_initialization(self, mock_ensemble):
        """测试 HybridRewardModelV2 初始化"""
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        mock_ensemble.return_value.predict.return_value = {}
        model = HybridRewardModelV2(
            weights={"real_world": 0.6, "quality": 0.3, "system_health": 0.1},
        )
        assert model.weights["real_world"] == 0.6
        assert model.weights["quality"] == 0.3
        assert model.weights["system_health"] == 0.1
