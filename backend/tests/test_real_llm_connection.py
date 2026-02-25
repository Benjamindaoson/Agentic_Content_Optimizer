"""
Stage 4 验证：真实 LLM 连接测试
"""

import pytest
import os
import logging
from app.agents.swarm.writer_agent import WriterAgent
from app.core.swarm_protocol import SwarmTask, AgentCapability

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_real_llm_generation():
    """
    测试 WriterAgent 是否能调用真实 LLM
    注意：这需要 OPENAI_API_KEY 环境变量
    """
    
    # 检查 Key 是否存在，不存在则跳过真实测试，只验证回退逻辑
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    has_key = bool(openai_key or deepseek_key)
    
    if not has_key:
        logger.warning("⚠️ 未检测到任何 API Key，将测试回退(Fallback)逻辑")
    else:
        logger.info("✅ 检测到 API Key，即将进行真实 API 调用...")

    agent = WriterAgent()
    task = SwarmTask(
        description="写一篇关于 'Python 3.13 新特性' 的技术笔记",
        required_capabilities=[AgentCapability.CONTENT_WRITING],
        context={"topic": "Python 3.13 新特性"}
    )
    
    result = await agent.execute(task, shared_memory={})
    content = result.output_data["content"]
    
    logger.info(f"生成标题: {content.get('title')}")
    logger.info(f"生成 Hook: {content.get('hook')}")
    
    # 验证结构
    assert "title" in content
    assert "hook" in content
    assert "body" in content
    
    # 如果有 Key，验证是否不再是模拟数据
    if has_key:
        assert "【模拟】" not in content["title"], "应当生成真实内容，但检测到了模拟标记"
        logger.info("🎉 真实 LLM 调用成功！")
    else:
        assert "【模拟】" in content["title"], "应当回退到模拟内容"
        logger.info("✅ 模拟回退逻辑验证成功")
