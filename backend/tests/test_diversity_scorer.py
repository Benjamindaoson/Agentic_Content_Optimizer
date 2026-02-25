"""
多样性评分器单元测试
"""

import pytest
import numpy as np
from app.ml.rl.diversity_scorer import DiversityScorer, DiversityConfig, cosine_sim

@pytest.mark.unit
@pytest.mark.rl
class TestDiversityScorer:
    
    @pytest.fixture
    def mock_embed_fn(self):
        """简单的 mock embedding 函数：将文本长度转为向量"""
        def embed(text: str):
            # 返回 4 维向量
            v = np.zeros(4)
            if "apple" in text: v[0] = 1.0
            if "banana" in text: v[1] = 1.0
            if "cat" in text: v[2] = 1.0
            if "dog" in text: v[3] = 1.0
            return v
        return embed

    @pytest.fixture
    def scorer(self, mock_embed_fn):
        config = DiversityConfig(
            near_dup_threshold=0.9,
            near_dup_penalty=0.8,
            strategy_freq_start=2,
            strategy_freq_penalty=0.5
        )
        return DiversityScorer(embed_fn=mock_embed_fn, config=config)

    def test_cosine_sim(self):
        a = np.array([1, 0, 0])
        b = np.array([1, 0, 0])
        c = np.array([0, 1, 0])
        assert cosine_sim(a, b) == pytest.approx(1.0)
        assert cosine_sim(a, c) == pytest.approx(0.0)

    def test_base_diversity_empty_ref(self, scorer):
        """无参考时，多样性为 1"""
        score = scorer.compute_diversity_score("apple", ("h1", "b1", "c1"))
        assert score == 1.0

    def test_content_similarity_penalty(self, scorer):
        """内容相似度惩罚测试"""
        scorer.add_reference("apple cat")
        
        # 1. 完全相同的内容 -> 应该受到强力惩罚
        score_same = scorer.compute_diversity_score("apple cat", ("h2", "b2", "c2"))
        assert score_same < 0.3
        
        # 2. 部分相似 -> 分数中等
        score_partial = scorer.compute_diversity_score("apple dog", ("h2", "b2", "c2"))
        # apple cat [1, 0, 1, 0] normalized: [0.707, 0, 0.707, 0]
        # apple dog [1, 0, 0, 1] normalized: [0.707, 0, 0, 0.707]
        # sim = 0.5
        assert 0.4 < score_partial < 0.6

        # 3. 完全不同 -> 分数接近 1
        score_diff = scorer.compute_diversity_score("banana dog", ("h2", "b2", "c2"))
        assert score_diff > 0.9

    def test_strategy_frequency_penalty(self, scorer):
        """策略频率惩罚测试"""
        strategy = ("hook_A", "body_B", "cta_C")
        
        # 第一次尝试，无惩罚
        score1 = scorer.compute_diversity_score("brand new text", strategy)
        assert score1 == 1.0
        
        # 更新频率
        scorer.update_strategy_count(strategy) # 1
        scorer.update_strategy_count(strategy) # 2
        
        # 达到 config.strategy_freq_start=2，开始惩罚
        score2 = scorer.compute_diversity_score("brand new text", strategy)
        assert score2 < 1.0
        
        scorer.update_strategy_count(strategy) # 3
        score3 = scorer.compute_diversity_score("brand new text", strategy)
        assert score3 < score2 # 惩罚加重

    def test_statistics(self, scorer):
        scorer.add_reference("test")
        scorer.update_strategy_count(("h", "b", "c"))
        stats = scorer.get_statistics()
        assert stats['total_references'] == 1
        assert stats['total_strategies'] == 1
        assert len(stats['most_used_strategies']) == 1
