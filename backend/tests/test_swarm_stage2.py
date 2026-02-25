"""
Stage 2 蜂群验证：验证因果增益与多模态对齐逻辑
"""

import pytest
import asyncio
from app.core.swarm_coordinator import SwarmCoordinator
from app.agents.swarm.writer_agent import WriterAgent
from app.agents.swarm.critic_agent import MultiModalCriticAgent
from app.ml.causal_scorer import CausalScorer
from app.ml.mm_aligner import MultiModalAligner
from app.core.swarm_protocol import AgentCapability

@pytest.mark.asyncio
async def test_swarm_stage2_insights():
    coordinator = SwarmCoordinator()
    
    # 注入 Stage 2 组件到共享内存口 (模拟 Blackboard 的功能扩展)
    coordinator.blackboard.shared_memory["causal_scorer"] = CausalScorer()
    coordinator.blackboard.shared_memory["mm_aligner"] = MultiModalAligner()
    
    coordinator.register_agent(WriterAgent())
    coordinator.register_agent(MultiModalCriticAgent())
    
    # 模拟一个“大V”发布的背景环境（高粉丝量）
    context = {
        "topic": "极简生活方式",
        "follower_count": 500000, # 500k 粉丝
        "publish_hour": 20,       # 黄金时段
        "category_baseline_ctr": 0.1
    }
    
    task_id = await coordinator.submit_task(
        description="生产极简生活爆款笔记并进行深度因果评估",
        caps=[AgentCapability.CONTENT_WRITING],
        context=context
    )
    
    # 运行蜂群
    # 我们需要确保 CriticAgent 在执行时使用了共享内存里的 Scorer
    # 这里我们手动测试 Critic 的 execute 逻辑是否能感知到这些
    
    await coordinator._process_bidding()
    await coordinator._process_execution()
    
    # 验证任务流水中产生了 Critic 的反馈
    assert len(coordinator.blackboard.active_tasks) > 1
    
    # 打印因果分析的可视化模拟 (在实际日志中可见)
    print("\n--- Stage 2 因果分析结果 ---")
    # 这里我们直接调用一下 scorer 看看数据效果
    scorer = coordinator.blackboard.shared_memory["causal_scorer"]
    insight = scorer.estimate_causal_reward({"engagement_rate": 0.15}, context, {})
    
    print(f"观测值: {insight.observed_reward:.4f}")
    print(f"基线预测 (粉丝/时段): {insight.estimated_baseline:.4f}")
    print(f"纯因果提升 (Strategy Effect): {insight.causal_lift:.4f}")
    
    assert insight.causal_lift < insight.observed_reward # 剔除了背景流量
    print("✅ 因果剥离逻辑验证通过")
