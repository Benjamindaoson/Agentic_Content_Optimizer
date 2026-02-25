"""
CriticAgent 单元测试

测试 CriticAgent 的核心功能：
1. 初始化
2. 内容评估
3. 多维度评分
4. 审批决策
5. 改进建议生成
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.content.critic_agent import CriticAgent
from app.agents.base import AgentConfig


class TestCriticAgentInitialization:
    """测试 CriticAgent 初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        agent = CriticAgent()

        assert agent.config.name == "CriticAgent"
        assert agent.config.temperature == 0.3
        assert agent.config.model == "claude-3-5-sonnet-20240620"

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = AgentConfig(
            name="CustomCriticAgent",
            description="自定义评估器",
            model="claude-3-opus-20240229",
            temperature=0.5
        )

        agent = CriticAgent(config=config)

        assert agent.config.name == "CustomCriticAgent"
        assert agent.config.temperature == 0.5


class TestCriticAgentExecute:
    """测试 CriticAgent 执行"""

    @pytest.mark.asyncio
    async def test_execute_missing_generated_contents(self):
        """测试缺少 generated_contents 参数"""
        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作工具"
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "generated_contents" in response.error.lower()

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_execute_success(self, mock_chat):
        """测试成功评估内容"""
        # Mock LLM 响应
        mock_chat.return_value = """
        {
            "creativity": 8.5,
            "executability": 9.0,
            "geo_optimization": 8.0,
            "platform_fit": 8.5,
            "engagement_potential": 9.0,
            "overall_score": 8.6,
            "decision": "APPROVED",
            "feedback": "内容质量优秀，创意新颖，执行性强。",
            "improvement_suggestions": []
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作工具推荐",
            "platform": "xiaohongshu",
            "generated_contents": [
                {
                    "hook": "你知道吗？AI 写作工具可以提升 10 倍效率",
                    "body": "AI 写作工具通过智能算法帮助你快速生成高质量内容",
                    "cta": "关注我，了解更多 AI 工具推荐",
                    "blueprint": {}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "evaluations" in response.data
        assert len(response.data["evaluations"]) > 0

        # 验证评估结果
        evaluation = response.data["evaluations"][0]
        assert "scores" in evaluation
        assert "decision" in evaluation
        assert "feedback" in evaluation
        assert evaluation["decision"] == "APPROVED"

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_execute_needs_revision(self, mock_chat):
        """测试需要修订的内容"""
        # Mock LLM 响应
        mock_chat.return_value = """
        {
            "creativity": 6.0,
            "executability": 7.0,
            "geo_optimization": 5.5,
            "platform_fit": 6.5,
            "engagement_potential": 6.0,
            "overall_score": 6.2,
            "decision": "NEEDS_REVISION",
            "feedback": "内容质量一般，需要改进创意和 GEO 优化。",
            "improvement_suggestions": [
                "增强 Hook 的吸引力",
                "优化 GEO 关键词覆盖",
                "改进 CTA 的行动号召"
            ]
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作工具",
            "platform": "xiaohongshu",
            "generated_contents": [
                {
                    "hook": "AI 写作工具",
                    "body": "这是一个 AI 工具",
                    "cta": "关注我",
                    "blueprint": {}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        evaluation = response.data["evaluations"][0]
        assert evaluation["decision"] == "NEEDS_REVISION"
        assert len(evaluation["improvement_suggestions"]) > 0

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_execute_rejected(self, mock_chat):
        """测试被拒绝的内容"""
        # Mock LLM 响应
        mock_chat.return_value = """
        {
            "creativity": 3.0,
            "executability": 4.0,
            "geo_optimization": 3.5,
            "platform_fit": 4.0,
            "engagement_potential": 3.5,
            "overall_score": 3.6,
            "decision": "REJECTED",
            "feedback": "内容质量不达标，需要重新生成。",
            "improvement_suggestions": [
                "完全重新构思内容",
                "增加创意元素",
                "优化平台适配性"
            ]
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {
                    "hook": "标题",
                    "body": "内容",
                    "cta": "关注",
                    "blueprint": {}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        evaluation = response.data["evaluations"][0]
        assert evaluation["decision"] == "REJECTED"
        assert evaluation["scores"]["overall_score"] < 5.0


class TestCriticAgentScoring:
    """测试评分功能"""

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_score_dimensions(self, mock_chat):
        """测试 5 个评分维度"""
        mock_chat.return_value = """
        {
            "creativity": 8.0,
            "executability": 9.0,
            "geo_optimization": 7.5,
            "platform_fit": 8.5,
            "engagement_potential": 8.0,
            "overall_score": 8.2,
            "decision": "APPROVED",
            "feedback": "各维度表现良好",
            "improvement_suggestions": []
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {
                    "hook": "测试",
                    "body": "内容",
                    "cta": "CTA",
                    "blueprint": {}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        scores = response.data["evaluations"][0]["scores"]

        # 验证所有维度都存在
        assert "creativity" in scores
        assert "executability" in scores
        assert "geo_optimization" in scores
        assert "platform_fit" in scores
        assert "engagement_potential" in scores
        assert "overall_score" in scores

        # 验证分数范围
        for dimension, score in scores.items():
            assert 0 <= score <= 10, f"{dimension} score out of range: {score}"

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_weighted_score_calculation(self, mock_chat):
        """测试加权总分计算"""
        mock_chat.return_value = """
        {
            "creativity": 8.0,
            "executability": 9.0,
            "geo_optimization": 7.0,
            "platform_fit": 8.0,
            "engagement_potential": 9.0,
            "overall_score": 8.2,
            "decision": "APPROVED",
            "feedback": "综合表现优秀",
            "improvement_suggestions": []
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {
                    "hook": "测试",
                    "body": "内容",
                    "cta": "CTA",
                    "blueprint": {}
                }
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        scores = response.data["evaluations"][0]["scores"]

        # 验证加权总分在合理范围内
        overall = scores["overall_score"]
        assert 7.0 <= overall <= 9.0


class TestCriticAgentMultipleContents:
    """测试多个内容评估"""

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_evaluate_multiple_contents(self, mock_chat):
        """测试评估多个内容"""
        # Mock LLM 响应（每次调用返回不同评分）
        mock_chat.side_effect = [
            '{"creativity": 8.0, "executability": 9.0, "geo_optimization": 7.5, "platform_fit": 8.5, "engagement_potential": 8.0, "overall_score": 8.2, "decision": "APPROVED", "feedback": "内容1优秀", "improvement_suggestions": []}',
            '{"creativity": 7.0, "executability": 8.0, "geo_optimization": 6.5, "platform_fit": 7.5, "engagement_potential": 7.0, "overall_score": 7.2, "decision": "NEEDS_REVISION", "feedback": "内容2需改进", "improvement_suggestions": ["优化创意"]}',
            '{"creativity": 9.0, "executability": 9.5, "geo_optimization": 8.5, "platform_fit": 9.0, "engagement_potential": 9.0, "overall_score": 9.0, "decision": "APPROVED", "feedback": "内容3卓越", "improvement_suggestions": []}'
        ]

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "内容1", "body": "正文1", "cta": "CTA1", "blueprint": {}},
                {"hook": "内容2", "body": "正文2", "cta": "CTA2", "blueprint": {}},
                {"hook": "内容3", "body": "正文3", "cta": "CTA3", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert len(response.data["evaluations"]) == 3

        # 验证每个评估都不同
        scores = [e["scores"]["overall_score"] for e in response.data["evaluations"]]
        assert len(set(scores)) == 3  # 3 个不同的分数


class TestCriticAgentDecisionLogic:
    """测试审批决策逻辑"""

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_decision_approved_threshold(self, mock_chat):
        """测试 APPROVED 决策阈值"""
        mock_chat.return_value = """
        {
            "creativity": 8.5,
            "executability": 9.0,
            "geo_optimization": 8.0,
            "platform_fit": 8.5,
            "engagement_potential": 9.0,
            "overall_score": 8.6,
            "decision": "APPROVED",
            "feedback": "达到批准标准",
            "improvement_suggestions": []
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        evaluation = response.data["evaluations"][0]
        assert evaluation["decision"] == "APPROVED"
        assert evaluation["scores"]["overall_score"] >= 8.0

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_decision_needs_revision_threshold(self, mock_chat):
        """测试 NEEDS_REVISION 决策阈值"""
        mock_chat.return_value = """
        {
            "creativity": 6.5,
            "executability": 7.0,
            "geo_optimization": 6.0,
            "platform_fit": 6.5,
            "engagement_potential": 6.5,
            "overall_score": 6.5,
            "decision": "NEEDS_REVISION",
            "feedback": "需要改进",
            "improvement_suggestions": ["优化创意", "增强吸引力"]
        }
        """

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True
        evaluation = response.data["evaluations"][0]
        assert evaluation["decision"] == "NEEDS_REVISION"
        assert 5.0 <= evaluation["scores"]["overall_score"] < 8.0


class TestCriticAgentErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_llm_error_handling(self, mock_chat):
        """测试 LLM 错误处理"""
        # Mock LLM 抛出异常
        mock_chat.side_effect = Exception("LLM API error")

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "error" in response.error.lower()

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_invalid_json_response(self, mock_chat):
        """测试无效 JSON 响应处理"""
        # Mock LLM 返回无效 JSON
        mock_chat.return_value = "这不是有效的 JSON"

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        # 应该处理 JSON 解析错误
        assert response.success is False or len(response.data.get("evaluations", [])) == 0


class TestCriticAgentPlatformSpecific:
    """测试平台特定评估"""

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_xiaohongshu_platform_evaluation(self, mock_chat):
        """测试小红书平台特定评估"""
        mock_chat.return_value = '{"creativity": 8.0, "executability": 9.0, "geo_optimization": 7.5, "platform_fit": 8.5, "engagement_potential": 8.0, "overall_score": 8.2, "decision": "APPROVED", "feedback": "适合小红书", "improvement_suggestions": []}'

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True

        # 验证调用 LLM 时包含平台信息
        call_args = mock_chat.call_args
        messages = call_args[1]["messages"]
        prompt = messages[0]["content"]

        assert "xiaohongshu" in prompt.lower() or "小红书" in prompt

    @pytest.mark.asyncio
    @patch('app.agents.content.critic_agent.ClaudeProvider.chat_completion')
    async def test_douyin_platform_evaluation(self, mock_chat):
        """测试抖音平台特定评估"""
        mock_chat.return_value = '{"creativity": 8.0, "executability": 9.0, "geo_optimization": 7.5, "platform_fit": 8.5, "engagement_potential": 8.0, "overall_score": 8.2, "decision": "APPROVED", "feedback": "适合抖音", "improvement_suggestions": []}'

        agent = CriticAgent()

        input_data = {
            "topic": "AI 写作",
            "platform": "douyin",
            "generated_contents": [
                {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}}
            ]
        }

        response = await agent.execute(input_data)

        assert response.success is True

        # 验证调用 LLM 时包含平台信息
        call_args = mock_chat.call_args
        messages = call_args[1]["messages"]
        prompt = messages[0]["content"]

        assert "douyin" in prompt.lower() or "抖音" in prompt
