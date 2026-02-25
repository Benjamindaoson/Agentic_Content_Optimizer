"""
EvolutionAgent: 策略优选与演化 Agent (Stage 3)

核心目标：基于世界模型的模拟结果，筛选并优化最佳策略，实现“优胜劣汰”。
"""

import logging
from typing import List, Optional, Any
from app.core.swarm_protocol import IAgent, SwarmTask, AgentBid, AgentResult, AgentCapability, SwarmTask, TaskPriority

logger = logging.getLogger(__name__)

class EvolutionAgent(IAgent):
    def __init__(self, agent_id: str = "evo_01"):
        self._agent_id = agent_id

    @property
    def agent_id(self) -> str: return self._agent_id

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.POLICY_OPTIMIZATION]

    async def bid(self, task: SwarmTask) -> Optional[AgentBid]:
        if "演化" in task.description or "预演" in task.description:
            return AgentBid(
                agent_id=self.agent_id,
                task_id=task.task_id,
                confidence_score=0.95,
                estimated_tokens=500,
                approach_summary="调用世界模型进行离线演练，识别并放大高表现特征。"
            )
        return None

    async def execute(self, task: SwarmTask, shared_memory: Any) -> AgentResult:
        content_candidates = task.context.get("candidates", [])
        
        logger.info(f"🧬 EvolutionAgent {self.agent_id} 正在启动策略演化程序...")
        
        world_model = shared_memory.get("world_model")
        dna_extractor = shared_memory.get("dna_extractor")
        
        if not world_model or not dna_extractor:
            return AgentResult(agent_id=self.agent_id, task_id=task.task_id, output_data={"error": "缺失世界模型或基因提取器"})
            
        # 1. 对候选内容进行模拟
        rankings = []
        for cand in content_candidates:
            # 提取 DNA
            dna = dna_extractor.extract_dna([{"content": cand}])
            # 模拟效果
            sim_result = world_model.simulate_rollout(cand, dna, task.context)
            rankings.append({
                "content": cand,
                "dna": dna,
                "sim_result": sim_result,
                "score": sim_result["simulated_engagement_rate"]
            })
            
        # 2. 选出最强者 (Survival of the fittest)
        rankings.sort(key=lambda x: x["score"], reverse=True)
        winner = rankings[0]
        
        # 3. 产生演化报告并决定是否需要“突变”
        should_mutate = winner["score"] < 0.12 # 如果最强的也不够强
        sub_tasks = []
        
        if should_mutate:
            sub_tasks.append(SwarmTask(
                description="策略突变：现有方案未能突破阈值，请求重构底层模式。",
                required_capabilities=[AgentCapability.CONTENT_WRITING],
                context={"directive": "强制尝试非线性视角", "prev_winner_dna": winner["dna"]}
            ))
            
        return AgentResult(
            agent_id=self.agent_id,
            task_id=task.task_id,
            output_data={
                "winner": winner,
                "evolution_status": "mutating" if should_mutate else "stable",
                "simulated_metrics": winner["sim_result"]
            },
            sub_tasks=sub_tasks
        )
