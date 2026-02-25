"""
Thompson Sampling 策略选择器单元测试
"""

import pytest
import numpy as np
from app.ml.rl.thompson_sampling import ThompsonSamplingSelector, ThompsonSamplingConfig, BanditArm

@pytest.mark.unit
@pytest.mark.rl
class TestBanditArm:
    """测试 BanditArm 基础统计记录"""
    
    def test_update_and_properties(self):
        arm = BanditArm()
        assert arm.n_pulls == 0
        assert arm.mean == 0.0
        assert arm.variance == 1.0 # 初始方差
        
        arm.update(10.0)
        assert arm.n_pulls == 1
        assert arm.mean == 10.0
        assert arm.variance == 1.0 # 样本小于2
        
        arm.update(20.0)
        assert arm.n_pulls == 2
        assert arm.mean == 15.0
        # mean_sq = 15^2 = 225
        # sum_reward_sq = 10^2 + 20^2 = 500
        # var = 500/2 - 225 = 250 - 225 = 25
        assert arm.variance == 25.0
        assert arm.std == 5.0

@pytest.mark.unit
@pytest.mark.rl
class TestThompsonSamplingSelector:
    """测试 ThompsonSamplingSelector"""
    
    @pytest.fixture
    def selector(self):
        # 3x2x2 = 12 种组合
        return ThompsonSamplingSelector(n_hooks=3, n_bodies=2, n_ctas=2)

    def test_initialization(self, selector):
        assert selector.n_hooks == 3
        assert selector.n_bodies == 2
        assert selector.n_ctas == 2
        assert selector.config.use_hierarchical is True

    def test_select_random(self, selector):
        action = selector.select_action(mode="random")
        assert len(action) == 3
        assert 0 <= action[0] < 3
        assert 0 <= action[1] < 2
        assert 0 <= action[2] < 2

    def test_cold_start_exploration(self, selector):
        """测试冷启动：优先探索未尝试过的臂"""
        # 强制执行 12 次选择，理应覆盖所有组合（或者至少在层级上覆盖所有分支）
        # 默认 min_pulls=3，所以前几次肯定会探索新臂
        actions = set()
        for _ in range(12):
            action = selector.select_action(mode="flat")
            actions.add(action)
            selector.update(action, 0.5) # 更新一下，n_pulls 增加
            
        # 在 flat 模式下，前 12 次如果不重复，应该覆盖全部
        assert len(actions) == 12

    def test_convergence_to_optimal(self):
        """测试收敛性：多次奖励后是否偏向最优策略"""
        selector = ThompsonSamplingSelector(n_hooks=2, n_bodies=1, n_ctas=1)
        # 最优策略为 (1, 0, 0)，给予高奖励
        # 次优策略为 (0, 0, 0)，给予低奖励
        
        optimal_action = (1, 0, 0)
        suboptimal_action = (0, 0, 0)
        
        # 模拟 100 轮
        for i in range(100):
            action = selector.select_action(mode="auto")
            if action == optimal_action:
                reward = np.random.normal(1.0, 0.1)
            else:
                reward = np.random.normal(0.2, 0.1)
            selector.update(action, reward)
            
        # 经过 100 轮训练，最佳动作应该是 (1, 0, 0)
        best_action = selector.get_best_action()
        assert best_action == optimal_action
        
        # 统计信息中，最优策略的尝试次数应该更多
        stats = selector.get_statistics()
        # 检查 top_triplets
        assert stats['top_triplets'][0][0] == optimal_action

    def test_hierarchical_selection(self, selector):
        """测试层级采样逻辑"""
        action = selector.select_action(mode="hierarchical")
        assert len(action) == 3
        
        # 更新一个特定的 hook
        selector.update((0, 0, 0), 10.0)
        # 再次选择，hook 0 的均值最高，理应更有可能选到 hook 0
        # (由于 TS 有随机性，这里虽然不保证 100% 选到，但在多次尝试中应该占主导)
        count = 0
        for _ in range(20):
            if selector.select_action(mode="hierarchical")[0] == 0:
                count += 1
        assert count > 10 # 大概率选到 hook 0

    def test_neighbor_prior(self):
        """测试近邻先验获取"""
        config = ThompsonSamplingConfig(use_neighbor_sharing=True, n_neighbors=2)
        # 2 hooks
        selector = ThompsonSamplingSelector(2, 1, 1, config=config)
        
        # 设置 dummy embeddings (2D)
        # Hook 0 and Hook 1 are close
        hook_embeds = np.array([[0.1, 0.1], [0.11, 0.11]])
        body_embeds = np.array([[0.5, 0.5]])
        cta_embeds = np.array([[0.5, 0.5]])
        selector.set_embeddings(hook_embeds, body_embeds, cta_embeds)
        
        # 给 Hook 0 喂点高奖励数据
        selector.update((0, 0, 0), 0.9)
        
        # 获取 Hook 1 的先验
        # 由于 Hook 1 和 Hook 0 很像，Hook 1 的先验点击率应该被 Hook 0 带动
        prior_mean, _ = selector.get_neighbor_prior((1, 0, 0))
        assert prior_mean > 0.6 # 应该大于默认的 0.5
