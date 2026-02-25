"""
Stage 4 验证：混合 LLM 策略连接测试 (DeepSeek + GPT-4o)
"""

import pytest
import os
import logging
from app.agents.swarm.writer_agent import WriterAgent
from app.agents.swarm.critic_agent import MultiModalCriticAgent
from app.core.swarm_protocol import SwarmTask, AgentCapability

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_hybrid_strategy_connection():
    """
    验证混合策略：
    1. Writer 使用 DeepSeek (DEEPSEEK_API_KEY)
    2. Critic 使用 GPT-4o (OPENAI_API_KEY)
    """
    
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    logger.info(f"🔑 DeepSeek Key Present: {bool(deepseek_key)}")
    logger.info(f"🔑 OpenAI Key Present: {bool(openai_key)}")

    # 1. 测试 Writer (DeepSeek)
    writer = WriterAgent()
    write_task = SwarmTask(
        description="写一句关于 '混合云架构' 的 Slogan",
        required_capabilities=[AgentCapability.CONTENT_WRITING],
        context={"topic": "混合云架构"}
    )
    
    w_result = await writer.execute(write_task, {})
    content = w_result.output_data["content"]
    logger.info(f"📝 DeepSeek 输出预览: {str(content)[:100]}...")
    
    if deepseek_key:
        assert "【模拟】" not in str(content), "Writer 应当使用真实 DeepSeek 生成"
    else:
        logger.warning("⚠️ 无 DeepSeek Key，Writer 回退到模拟/OpenAI模式")

    # 2. 测试 Critic (DeepSeek Text)
    critic = MultiModalCriticAgent()
    critic_task = SwarmTask(
        description="评估上述内容",
        required_capabilities=[AgentCapability.CRITIC_QUALITY],
        context={"content": content}
    )
    
    c_result = await critic.execute(critic_task, {})
    scores = c_result.output_data["scores"]
    logger.info(f"👁️ Critic 评分概览: {scores}")
    
    if deepseek_key:
        assert "deepseek_text_score" in scores, "Critic 应当包含 DeepSeek 文本评分"
    else:
        logger.warning("⚠️ 无 DeepSeek Key，Critic 回退到基础评分")
