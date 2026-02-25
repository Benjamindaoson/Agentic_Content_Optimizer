"""
Agent 工作流端到端集成测试 (Mock 版)

验证 Trend -> Writer -> Critic -> Refine 这一核心闭环。
使用 Mock LLM 避免产生费用并保证测试可重复。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# 假设核心入口在 viral_generator.py 或者通过 LangGraph node 触发
# 我们这里测试一个高层的 Agent 协作逻辑

@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentWorkflow:

    async def test_full_generation_loop(self):
        """测试从话题到内容的完整生成循环"""
        
        # 1. Mock 各个 Agent
        # Trend Agent: 提供话题热度建议
        with patch("app.agents.trend_agent.TrendAgent.analyze_topic", new_callable=AsyncMock) as mock_trend:
            mock_trend.return_value = {"hot_score": 0.85, "suggestions": ["使用悬念标题"]}
            
            # Writer Agent: 生成初稿
            with patch("app.agents.writer_agent.WriterAgent.generate_content", new_callable=AsyncMock) as mock_writer:
                mock_writer.return_value = {
                    "title": "初稿标题",
                    "text": "这是初稿内容...",
                    "action": (1, 2, 3)
                }
                
                # Critic Agent: 评估内容
                with patch("app.agents.critic_agent.CriticAgent.evaluate", new_callable=AsyncMock) as mock_critic:
                    # 第一次评估给低分，触发 Refine
                    # 第二次评估给高分，结束
                    mock_critic.side_effect = [
                        {"score": 0.4, "feedback": "内容太干，不够吸引人", "recommend_refine": True},
                        {"score": 0.85, "feedback": "完美", "recommend_refine": False}
                    ]
                    
                    # Refiner Agent: 修改内容
                    with patch("app.agents.refiner_agent.RefinerAgent.refine", new_callable=AsyncMock) as mock_refine:
                        mock_refine.return_value = {
                            "title": "优化后标题",
                            "text": "这是优化后的精彩内容...",
                            "action": (1, 2, 3)
                        }

                        # 执行主体逻辑 (这里模拟 API 调用的内部流程)
                        # 为了演示，我们假设有一个 ViralGenerator.run()
                        from app.generators.viral_generator import ViralGenerator
                        generator = ViralGenerator()
                        
                        # 注入 mock 依赖 (如果不是通过 patch)
                        # ...
                        
                        result = await generator.generate_viral_content(
                            category="美妆",
                            topic="晚霜测评"
                        )
                        
                        # 4. 验证
                        assert result["status"] == "success"
                        assert "优化后标题" in result["content"]["title"]
                        assert mock_writer.called
                        assert mock_critic.call_count == 2 # 触发了一次 refine
                        assert mock_refine.called

    async def test_workflow_error_handling(self):
        """测试工作流中的错误处理和降级"""
        
        # 模拟 LLM 超时或挂掉
        with patch("app.llm.unified.UnifiedLLM.agenerate", side_effect=Exception("LLM Timeout")):
            from app.generators.viral_generator import ViralGenerator
            generator = ViralGenerator()
            
            # 应该捕获异常并返回错误响应或降级内容
            try:
                result = await generator.generate_viral_content("测试", "测试")
                assert result["status"] == "error"
                assert "LLM Timeout" in result["message"]
            except Exception:
                pytest.fail("Workflow should handle internal exceptions gracefully")
