"""
DirectorAgent 单元测试

测试 DirectorAgent 的核心功能：
1. 初始化
2. 策略采样
3. ε-greedy 探索
4. 微创新变异
5. 多样性计算
"""

import pytest
from unittest.mock import patch

from app.agents.content.director_agent import DirectorAgent
from app.agents.base import AgentConfig


class TestDirectorAgentInitialization:
    """测试 DirectorAgent 初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        agent = DirectorAgent()

        assert agent.config.name == "DirectorAgent"
        assert agent.epsilon == 0.1  # ε-greedy 参数
        assert agent.mutation_rate == 0.3

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = AgentConfig(
            name="CustomDirectorAgent",
            description="自定义策略导演"
        )

        agent = DirectorAgent(
            config=config,
            epsilon=0.2,
            mutation_rate=0.4
        )

        assert agent.config.name == "CustomDirectorAgent"
        assert agent.epsilon == 0.2
        assert agent.mutation_rate == 0.4


class TestDirectorAgentExecute:
    """测试 DirectorAgent 执行"""

    @pytest.mark.asyncio
    async def test_execute_missing_references(self):
        """测试缺少 references 参数"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作工具"
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "references" in response.error.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功采样策略"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作工具",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {
                        "hook": "H01",
                        "body": "B02",
                        "cta": "C01"
                    }
                },
                {
                    "ref_id": "ref_2",
                    "structure": {
                        "hook": "H02",
                        "body": "B01",
                        "cta": "C02"
                    }
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "strategy" in response.data
        assert "hook" in response.data["strategy"]
        assert "body" in response.data["strategy"]
        assert "cta" in response.data["strategy"]

    @pytest.mark.asyncio
    async def test_execute_multiple_strategies(self):
        """测试生成多个策略"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ],
            "num_strategies": 5
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "strategies" in response.data
        assert len(response.data["strategies"]) == 5

        # 验证每个策略都有完整结构
        for strategy in response.data["strategies"]:
            assert "hook" in strategy
            assert "body" in strategy
            assert "cta" in strategy


class TestDirectorAgentSampling:
    """测试策略采样"""

    @pytest.mark.asyncio
    async def test_exploitation_sampling(self):
        """测试利用采样（基于参考内容）"""
        agent = DirectorAgent(epsilon=0.0)  # 禁用探索

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        strategy = response.data["strategy"]

        # 应该基于参考内容采样
        assert strategy["hook"] in ["H01", "H02", "H03"]  # 可能有微创新
        assert strategy["body"] in ["B01", "B02", "B03"]
        assert strategy["cta"] in ["C01", "C02", "C03"]

    @pytest.mark.asyncio
    async def test_exploration_sampling(self):
        """测试探索采样（随机）"""
        agent = DirectorAgent(epsilon=1.0)  # 完全探索

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        strategy = response.data["strategy"]

        # 应该随机采样
        assert strategy["hook"] is not None
        assert strategy["body"] is not None
        assert strategy["cta"] is not None


class TestDirectorAgentMutation:
    """测试微创新变异"""

    @pytest.mark.asyncio
    async def test_mutation_applied(self):
        """测试微创新变异应用"""
        agent = DirectorAgent(mutation_rate=1.0)  # 100% 变异率

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ]
        }

        # 运行多次，验证变异
        strategies = []
        for _ in range(10):
            response = await agent.execute(input_data)
            strategies.append(response.data["strategy"])

        # 应该有多样性（不是所有策略都相同）
        unique_strategies = len(set(
            (s["hook"], s["body"], s["cta"]) for s in strategies
        ))
        assert unique_strategies > 1  # 至少有 2 种不同的策略

    @pytest.mark.asyncio
    async def test_no_mutation(self):
        """测试无变异"""
        agent = DirectorAgent(mutation_rate=0.0, epsilon=0.0)  # 无变异，无探索

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        strategy = response.data["strategy"]

        # 应该直接使用参考内容的结构
        assert strategy["hook"] == "H01"
        assert strategy["body"] == "B02"
        assert strategy["cta"] == "C01"


class TestDirectorAgentDiversity:
    """测试多样性计算"""

    @pytest.mark.asyncio
    async def test_diversity_score_calculation(self):
        """测试多样性分数计算"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                },
                {
                    "ref_id": "ref_2",
                    "structure": {"hook": "H02", "body": "B01", "cta": "C02"}
                },
                {
                    "ref_id": "ref_3",
                    "structure": {"hook": "H03", "body": "B03", "cta": "C03"}
                }
            ],
            "num_strategies": 5
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "diversity_score" in response.data
        assert 0 <= response.data["diversity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_high_diversity(self):
        """测试高多样性"""
        agent = DirectorAgent(mutation_rate=0.8)  # 高变异率

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ],
            "num_strategies": 10
        }

        response = await agent.execute(input_data)

        assert response.success is True
        # 高变异率应该产生高多样性
        assert response.data["diversity_score"] > 0.5

    @pytest.mark.asyncio
    async def test_low_diversity(self):
        """测试低多样性"""
        agent = DirectorAgent(mutation_rate=0.0, epsilon=0.0)  # 无变异，无探索

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ],
            "num_strategies": 10
        }

        response = await agent.execute(input_data)

        assert response.success is True
        # 无变异应该产生低多样性
        assert response.data["diversity_score"] < 0.3


class TestDirectorAgentActionSpace:
    """测试动作空间"""

    @pytest.mark.asyncio
    async def test_valid_action_space(self):
        """测试有效的动作空间"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        strategy = response.data["strategy"]

        # 验证动作空间的有效性
        valid_hooks = [f"H{i:02d}" for i in range(1, 11)]  # H01-H10
        valid_bodies = [f"B{i:02d}" for i in range(1, 11)]  # B01-B10
        valid_ctas = [f"C{i:02d}" for i in range(1, 11)]  # C01-C10

        assert strategy["hook"] in valid_hooks
        assert strategy["body"] in valid_bodies
        assert strategy["cta"] in valid_ctas


class TestDirectorAgentErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_empty_references(self):
        """测试空参考列表"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作",
            "references": []
        }

        response = await agent.execute(input_data)

        # 应该能处理空参考列表（使用随机采样）
        assert response.success is True
        assert "strategy" in response.data

    @pytest.mark.asyncio
    async def test_invalid_reference_structure(self):
        """测试无效的参考结构"""
        agent = DirectorAgent()

        input_data = {
            "topic": "AI 写作",
            "references": [
                {
                    "ref_id": "ref_1",
                    "structure": {}  # 空结构
                }
            ]
        }

        response = await agent.execute(input_data)

        # 应该能处理无效结构（使用随机采样）
        assert response.success is True
        assert "strategy" in response.data
