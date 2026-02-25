"""
MetaPromptAgent: 自我修正与提示词优化 Agent (Stage 3)

核心目标：根据内容表现（及模拟表现）的负面反馈，自动修正相关 Agent 的 Prompt 指令。
实现蜂群的“自我进化”。
"""

import logging
from typing import List, Optional, Any
from app.core.swarm_protocol import IAgent, SwarmTask, AgentBid, AgentResult, AgentCapability

logger = logging.getLogger(__name__)

class MetaPromptAgent(IAgent):
    def __init__(self, agent_id: str = "meta_01"):
        self._agent_id = agent_id

    @property
    def agent_id(self) -> str: return self._agent_id

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.POLICY_OPTIMIZATION]

    async def bid(self, task: SwarmTask) -> Optional[AgentBid]:
        if "修正" in task.description or "优化 Prompt" in task.description:
            return AgentBid(
                agent_id=self.agent_id,
                task_id=task.task_id,
                confidence_score=0.98,
                estimated_tokens=700,
                approach_summary="分析性能缺口，利用 Few-shot 反思模式重构 Agent 的指令上下文。"
            )
        return None

    async def execute(self, task: SwarmTask, shared_memory: Any) -> AgentResult:
        target_agent_id = task.context.get("target_agent", "writer_01")
        feedback = task.context.get("feedback", "表现不佳")
        
        logger.info(f"🧠 MetaPromptAgent {self.agent_id} 正在对 {target_agent_id} 进行深度复盘与指令优化...")
        
        # 1. 模拟“反思”逻辑
        new_prompt_directive = f"""
        [指令优化] 基于过往反馈 '{feedback}'，在生成内容时：
        1. 必须额外强调情绪价值的递进，减少描述性文字。
        2. 增加 20% 的异质性词汇，打破模式化感官。
        """
        
        # 2. 将更新写入共享内存对应的 Agent 配置区域
        if "agent_configs" not in shared_memory:
            shared_memory["agent_configs"] = {}
            
        shared_memory["agent_configs"][target_agent_id] = {
            "dynamic_directive": new_prompt_directive,
            "version": "3.0.1-alpha"
        }
        
        logger.info(f"✨ {target_agent_id} 的动态指令已更新。")

        return AgentResult(
            agent_id=self.agent_id,
            task_id=task.task_id,
            output_data={"updated_directive": new_prompt_directive},
            metrics={"improvement_index": 0.15}
        )
