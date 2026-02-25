"""
Stage 1 冒烟测试：验证 Agent Mesh 蜂群协作逻辑
"""

import pytest
import asyncio
from app.core.swarm_coordinator import SwarmCoordinator
from app.agents.swarm.writer_agent import WriterAgent
from app.agents.swarm.critic_agent import MultiModalCriticAgent
from app.core.swarm_protocol import AgentCapability

@pytest.mark.asyncio
async def test_swarm_workflow_basic():
    # 1. 初始化协调器
    coordinator = SwarmCoordinator()
    
    # 2. 注册 Agents
    coordinator.register_agent(WriterAgent())
    coordinator.register_agent(MultiModalCriticAgent())
    
    # 3. 提交初始任务
    task_id = await coordinator.submit_task(
        description="写一篇关于 'AI 智能体未来' 的小红书笔记",
        caps=[AgentCapability.CONTENT_WRITING],
        context={"topic": "AI 智能体未来"}
    )
    
    # 4. 运行蜂群 (设置最大轮数防止死循环)
    max_rounds = 5
    for i in range(max_rounds):
        print(f"\n--- Round {i+1} ---")
        await coordinator._process_bidding()
        await coordinator._process_execution()
        
        # 检查初始任务是否完成
        if coordinator.blackboard.active_tasks[task_id].status == "completed":
            print("🎉 初始任务已完成")
            break
            
    # 验证产生的结果
    assert coordinator.blackboard.active_tasks[task_id].status == "completed"
    assert len(coordinator.blackboard.completed_tasks) >= 1
    
    # 验证是否产生了子任务 (Critic 或 Visual)
    has_subtasks = len(coordinator.blackboard.active_tasks) > 1
    assert has_subtasks
    print(f"📊 蜂群共处理了 {len(coordinator.blackboard.active_tasks)} 个任务")
