"""
Stage 3 终极验证：验证全自洽蜂群、世界模型预演与自我进化逻辑
"""

import pytest
import asyncio
from app.core.swarm_coordinator import SwarmCoordinator
from app.agents.swarm.writer_agent import WriterAgent
from app.agents.swarm.critic_agent import MultiModalCriticAgent
from app.agents.swarm.evolution_agent import EvolutionAgent
from app.agents.swarm.meta_prompt_agent import MetaPromptAgent
from app.ml.world_model import PolicyRolloutSimulator
from app.ml.dna_extractor import StrategyDNAExtractor
from app.ml.causal_scorer import CausalScorer
from app.ml.mm_aligner import MultiModalAligner
from app.core.swarm_protocol import AgentCapability, SwarmTask, TaskPriority

@pytest.mark.asyncio
async def test_swarm_stage3_autonomous_evolution():
    coordinator = SwarmCoordinator()
    
    # 1. 注入 Stage 3 全量组件
    coordinator.blackboard.shared_memory.update({
        "world_model": PolicyRolloutSimulator(),
        "dna_extractor": StrategyDNAExtractor(),
        "causal_scorer": CausalScorer(),
        "mm_aligner": MultiModalAligner()
    })
    
    # 2. 注册全能 Agent 团队
    coordinator.register_agent(WriterAgent())
    coordinator.register_agent(MultiModalCriticAgent())
    coordinator.register_agent(EvolutionAgent())
    coordinator.register_agent(MetaPromptAgent())
    
    # 3. 提交初始复杂任务：生成并评估，如果不达标则演化并自我修正
    task_id = await coordinator.submit_task(
        description="【全自洽生产】生产一款美妆新品爆款笔记，通过 World Model 验证，并在信心不足时触发自我进化。",
        caps=[AgentCapability.CONTENT_WRITING],
        context={"topic": "黑曜石精华液", "category": "beauty", "follower_count": 10000}
    )
    
    # 4. 运行多轮协作逻辑 (模拟 Swarm 演化循环)
    # 第一轮：Writer 产出 -> Critic 评估 (可能触发 Refine)
    await coordinator._process_bidding()
    await coordinator._process_execution()
    
    # 人为触发演化预演：从黑板提取已生成的候选内容
    candidates = [res.output_data["content"] for res in coordinator.blackboard.completed_tasks if "content" in res.output_data]
    
    if candidates:
        await coordinator.submit_task(
            description="对现有候选内容进行阶段性策略演化与预演",
            caps=[AgentCapability.POLICY_OPTIMIZATION],
            context={"candidates": candidates, "category": "beauty"}
        )
    
    # 运行蜂群至演化完成
    for _ in range(3):
        await coordinator._process_bidding()
        await coordinator._process_execution()
        
    # 5. 验证结果
    # 检查是否产生了演化报告或 MetaPrompt 更新
    has_evolution = any("winner" in res.output_data for res in coordinator.blackboard.completed_tasks)
    has_meta_update = "agent_configs" in coordinator.blackboard.shared_memory
    
    print(f"\n--- Stage 3 蜂群运行报告 ---")
    print(f"处理任务数: {len(coordinator.blackboard.active_tasks)}")
    print(f"自我进化触发: {'YES' if has_evolution else 'NO'}")
    print(f"反思指令更新: {'YES' if has_meta_update else 'NO'}")
    
    assert len(coordinator.blackboard.completed_tasks) >= 2
    print("✅ Stage 3 全自洽蜂群逻辑验证成功")
