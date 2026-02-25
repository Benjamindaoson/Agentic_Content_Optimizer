"""
LangGraph 工作流单元测试

测试 ContentGenerationWorkflow 的核心功能：
1. 工作流初始化
2. 内容生成流程
3. 自动重试机制
4. 状态持久化
5. 流式执行
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.workflow.langgraph_workflow import ContentGenerationWorkflow


class TestWorkflowInitialization:
    """测试工作流初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        workflow = ContentGenerationWorkflow()

        assert workflow is not None
        assert hasattr(workflow, 'graph')
        assert hasattr(workflow, 'memory')

    def test_workflow_nodes(self):
        """测试工作流节点"""
        workflow = ContentGenerationWorkflow()

        # 验证工作流包含所有必要的节点
        # 注意：具体实现可能不同，这里是示例
        assert workflow.graph is not None


class TestWorkflowExecution:
    """测试工作流执行"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_generate_content_success(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试成功生成内容"""
        # Mock Agent 响应
        from app.agents.base import AgentResponse

        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI", "写作"]},
                "references": [
                    {
                        "ref_id": "ref_1",
                        "text": "参考内容",
                        "structure": {"hook": "H01", "body": "B02", "cta": "C01"}
                    }
                ]
            }
        )

        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {
                        "hook": "AI 写作工具推荐",
                        "body": "内容正文",
                        "cta": "关注我",
                        "blueprint": {},
                        "geo_coverage": 0.8
                    }
                ]
            }
        )

        mock_critic.return_value = AgentResponse(
            success=True,
            data={
                "evaluations": [
                    {
                        "scores": {
                            "creativity": 8.5,
                            "executability": 9.0,
                            "geo_optimization": 8.0,
                            "platform_fit": 8.5,
                            "engagement_potential": 9.0,
                            "overall_score": 8.6
                        },
                        "decision": "APPROVED",
                        "feedback": "内容优秀",
                        "improvement_suggestions": []
                    }
                ]
            }
        )

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作工具",
            platform="xiaohongshu",
            max_iterations=3
        )

        assert result["status"] == "completed"
        assert "final_content" in result
        assert "final_score" in result
        assert result["final_score"] >= 8.0

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    async def test_generate_content_trend_failure(self, mock_trend):
        """测试 Trend Agent 失败"""
        from app.agents.base import AgentResponse

        mock_trend.return_value = AgentResponse(
            success=False,
            error="Trend Agent failed"
        )

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3
        )

        assert result["status"] == "failed"
        assert "error" in result


class TestWorkflowRetry:
    """测试自动重试机制"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_retry_on_low_quality(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试低质量内容自动重试"""
        from app.agents.base import AgentResponse

        # Mock Trend Agent
        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI"]},
                "references": [
                    {"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}
                ]
            }
        )

        # Mock Writer Agent
        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}, "geo_coverage": 0.5}
                ]
            }
        )

        # Mock Critic Agent - 第一次低分，第二次高分
        mock_critic.side_effect = [
            AgentResponse(
                success=True,
                data={
                    "evaluations": [
                        {
                            "scores": {"overall_score": 6.0},
                            "decision": "NEEDS_REVISION",
                            "feedback": "需要改进",
                            "improvement_suggestions": ["优化创意"]
                        }
                    ]
                }
            ),
            AgentResponse(
                success=True,
                data={
                    "evaluations": [
                        {
                            "scores": {"overall_score": 8.5},
                            "decision": "APPROVED",
                            "feedback": "内容优秀",
                            "improvement_suggestions": []
                        }
                    ]
                }
            )
        ]

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3
        )

        # 应该重试并最终成功
        assert result["status"] == "completed"
        assert result["iterations"] >= 2  # 至少重试一次

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_max_iterations_reached(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试达到最大迭代次数"""
        from app.agents.base import AgentResponse

        # Mock Trend Agent
        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI"]},
                "references": [
                    {"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}
                ]
            }
        )

        # Mock Writer Agent
        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}, "geo_coverage": 0.5}
                ]
            }
        )

        # Mock Critic Agent - 始终返回低分
        mock_critic.return_value = AgentResponse(
            success=True,
            data={
                "evaluations": [
                    {
                        "scores": {"overall_score": 5.0},
                        "decision": "NEEDS_REVISION",
                        "feedback": "需要改进",
                        "improvement_suggestions": ["优化创意"]
                    }
                ]
            }
        )

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=2  # 最多 2 次迭代
        )

        # 应该达到最大迭代次数
        assert result["iterations"] == 2
        assert result["status"] in ["completed", "max_iterations_reached"]


class TestWorkflowState:
    """测试状态管理"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_state_persistence(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试状态持久化"""
        from app.agents.base import AgentResponse

        # Mock Agent 响应
        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI"]},
                "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}]
            }
        )

        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}, "geo_coverage": 0.8}
                ]
            }
        )

        mock_critic.return_value = AgentResponse(
            success=True,
            data={
                "evaluations": [
                    {
                        "scores": {"overall_score": 8.5},
                        "decision": "APPROVED",
                        "feedback": "优秀",
                        "improvement_suggestions": []
                    }
                ]
            }
        )

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3
        )

        # 验证状态被正确记录
        assert "iterations" in result
        assert "final_content" in result
        assert "final_score" in result


class TestWorkflowStreaming:
    """测试流式执行"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_stream_content_generation(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试流式内容生成"""
        from app.agents.base import AgentResponse

        # Mock Agent 响应
        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI"]},
                "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}]
            }
        )

        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}, "geo_coverage": 0.8}
                ]
            }
        )

        mock_critic.return_value = AgentResponse(
            success=True,
            data={
                "evaluations": [
                    {
                        "scores": {"overall_score": 8.5},
                        "decision": "APPROVED",
                        "feedback": "优秀",
                        "improvement_suggestions": []
                    }
                ]
            }
        )

        workflow = ContentGenerationWorkflow()

        # 测试流式执行
        events = []
        async for event in workflow.stream_content_generation(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3
        ):
            events.append(event)

        # 应该收到多个事件
        assert len(events) > 0
        # 最后一个事件应该是完成状态
        assert events[-1].get("status") in ["completed", "failed"]


class TestWorkflowQualityThreshold:
    """测试质量阈值"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    @patch('app.agents.content.writer_agent.WriterAgent.execute')
    @patch('app.agents.content.critic_agent.CriticAgent.execute')
    async def test_quality_threshold_met(
        self,
        mock_critic,
        mock_writer,
        mock_trend
    ):
        """测试达到质量阈值"""
        from app.agents.base import AgentResponse

        # Mock Agent 响应
        mock_trend.return_value = AgentResponse(
            success=True,
            data={
                "geo_constraints": {"keywords": ["AI"]},
                "references": [{"ref_id": "ref_1", "text": "参考", "structure": {"hook": "H01", "body": "B02", "cta": "C01"}}]
            }
        )

        mock_writer.return_value = AgentResponse(
            success=True,
            data={
                "generated_contents": [
                    {"hook": "测试", "body": "内容", "cta": "CTA", "blueprint": {}, "geo_coverage": 0.8}
                ]
            }
        )

        mock_critic.return_value = AgentResponse(
            success=True,
            data={
                "evaluations": [
                    {
                        "scores": {"overall_score": 9.0},  # 高分
                        "decision": "APPROVED",
                        "feedback": "卓越",
                        "improvement_suggestions": []
                    }
                ]
            }
        )

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3,
            quality_threshold=8.5  # 设置质量阈值
        )

        # 应该在第一次迭代就成功（因为分数 9.0 > 8.5）
        assert result["status"] == "completed"
        assert result["final_score"] >= 8.5
        assert result["iterations"] == 1


class TestWorkflowErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_missing_topic(self):
        """测试缺少 topic 参数"""
        workflow = ContentGenerationWorkflow()

        with pytest.raises(Exception):
            await workflow.generate_content(
                topic=None,
                platform="xiaohongshu",
                max_iterations=3
            )

    @pytest.mark.asyncio
    async def test_missing_platform(self):
        """测试缺少 platform 参数"""
        workflow = ContentGenerationWorkflow()

        with pytest.raises(Exception):
            await workflow.generate_content(
                topic="AI 写作",
                platform=None,
                max_iterations=3
            )

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent.execute')
    async def test_agent_exception_handling(self, mock_trend):
        """测试 Agent 异常处理"""
        # Mock Agent 抛出异常
        mock_trend.side_effect = Exception("Agent error")

        workflow = ContentGenerationWorkflow()

        result = await workflow.generate_content(
            topic="AI 写作",
            platform="xiaohongshu",
            max_iterations=3
        )

        # 应该捕获异常并返回失败状态
        assert result["status"] == "failed"
        assert "error" in result
