"""
Advanced Agent System
先进的智能体系统 (2025-2026 前沿技术)

特性:
1. Self-Reflection (自我反思)
2. Chain-of-Thought (思维链)
3. Tree-of-Thoughts (思维树)
4. Agent Communication Protocol (智能体通信)
5. Memory System (记忆系统)
6. Tool Learning (工具学习)
"""

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime
import json

from app.engine.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.engine.llm.unified import unified_llm

logger = logging.getLogger(__name__)


class ThinkingMode(str, Enum):
    """思考模式"""
    DIRECT = "direct"  # 直接回答
    COT = "chain_of_thought"  # 思维链
    TOT = "tree_of_thoughts"  # 思维树
    REFLECTION = "reflection"  # 自我反思


class AdvancedAgent(BaseAgent):
    """
    先进智能体

    核心能力:
    1. 多种思考模式 (CoT, ToT, Reflection)
    2. 自主决策和规划
    3. 工具学习和使用
    4. 记忆管理
    5. 与其他 Agent 通信
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)

        # 记忆系统
        self.short_term_memory = []  # 短期记忆 (当前对话)
        self.long_term_memory = {}   # 长期记忆 (持久化)
        self.working_memory = {}     # 工作记忆 (临时计算)

        # 工具库
        self.tools = {}

        # 通信协议
        self.message_queue = []

    async def execute(
        self,
        input_data: Dict[str, Any],
        thinking_mode: ThinkingMode = ThinkingMode.COT
    ) -> AgentResponse:
        """
        执行任务 (支持多种思考模式)

        Args:
            input_data: 输入数据
            thinking_mode: 思考模式

        Returns:
            AgentResponse
        """
        try:
            # 1. 存储到短期记忆
            self._store_short_term_memory(input_data)

            # 2. 根据思考模式执行
            if thinking_mode == ThinkingMode.DIRECT:
                result = await self._direct_execution(input_data)
            elif thinking_mode == ThinkingMode.COT:
                result = await self._chain_of_thought(input_data)
            elif thinking_mode == ThinkingMode.TOT:
                result = await self._tree_of_thoughts(input_data)
            elif thinking_mode == ThinkingMode.REFLECTION:
                result = await self._reflection_execution(input_data)
            else:
                result = await self._direct_execution(input_data)

            # 3. 存储结果到记忆
            self._store_long_term_memory(input_data, result)

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "agent": self.config.name,
                    "thinking_mode": thinking_mode.value
                }
            )

        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    async def _chain_of_thought(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chain-of-Thought (思维链)

        让 LLM 逐步推理，提升复杂任务性能

        示例:
        Q: 生成一个健身内容
        CoT:
        1. 首先，我需要了解目标受众...
        2. 然后，我需要选择合适的 Hook...
        3. 接下来，我需要构建 Body...
        4. 最后，我需要添加 CTA...
        """
        prompt = f"""Task: {input_data.get('task', 'Execute task')}

Context: {json.dumps(input_data, ensure_ascii=False, indent=2)}

Please solve this task step by step:
1. First, analyze the requirements
2. Then, break down the task into sub-tasks
3. Next, solve each sub-task
4. Finally, combine the results

Think through each step carefully and explain your reasoning.

Respond in JSON format:
{{
  "steps": [
    {{"step": 1, "thought": "...", "action": "...", "result": "..."}},
    ...
  ],
  "final_result": {{...}}
}}"""

        try:
            response = await unified_llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={
                    "steps": "array",
                    "final_result": "object"
                },
                provider="claude",
                model="sonnet-4.5",
                temperature=0.7
            )

            return response

        except Exception as e:
            logger.error(f"Chain-of-Thought error: {e}")
            return {"error": str(e)}

    async def _tree_of_thoughts(
        self,
        input_data: Dict[str, Any],
        num_branches: int = 3,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Tree-of-Thoughts (思维树)

        探索多个推理路径，选择最优解

        算法:
        1. 生成多个初始想法 (branches)
        2. 对每个想法进行评估
        3. 选择最优的想法继续扩展
        4. 重复直到达到深度限制
        5. 返回最优路径
        """
        # 初始化思维树
        tree = {
            "root": input_data,
            "branches": [],
            "best_path": []
        }

        current_nodes = [{"thought": "Initial state", "data": input_data, "score": 0.0}]

        # 逐层扩展
        for level in range(depth):
            next_nodes = []

            for node in current_nodes:
                # 生成多个分支
                branches = await self._generate_branches(
                    node["data"],
                    num_branches=num_branches
                )

                # 评估每个分支
                for branch in branches:
                    score = await self._evaluate_thought(branch)
                    next_nodes.append({
                        "thought": branch["thought"],
                        "data": branch["data"],
                        "score": score,
                        "parent": node
                    })

            # 选择最优的 num_branches 个节点继续扩展
            next_nodes.sort(key=lambda x: x["score"], reverse=True)
            current_nodes = next_nodes[:num_branches]

            tree["branches"].append(current_nodes)

        # 选择最优路径
        best_node = max(current_nodes, key=lambda x: x["score"])

        # 回溯路径
        path = []
        node = best_node
        while node:
            path.insert(0, {
                "thought": node["thought"],
                "score": node["score"]
            })
            node = node.get("parent")

        tree["best_path"] = path

        return {
            "tree": tree,
            "final_result": best_node["data"],
            "best_score": best_node["score"]
        }

    async def _generate_branches(
        self,
        current_state: Dict[str, Any],
        num_branches: int = 3
    ) -> List[Dict[str, Any]]:
        """生成思维分支"""
        prompt = f"""Current state: {json.dumps(current_state, ensure_ascii=False)}

Generate {num_branches} different approaches to solve this task.
Each approach should be creative and distinct.

Respond in JSON format:
{{
  "branches": [
    {{"thought": "Approach 1 description", "data": {{...}}}},
    {{"thought": "Approach 2 description", "data": {{...}}}},
    ...
  ]
}}"""

        try:
            response = await unified_llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"branches": "array"},
                provider="claude",
                model="sonnet-4.5",
                temperature=0.9  # 高温度鼓励多样性
            )

            return response.get("branches", [])

        except Exception as e:
            logger.error(f"Generate branches error: {e}")
            return []

    async def _evaluate_thought(self, thought: Dict[str, Any]) -> float:
        """评估思维质量"""
        prompt = f"""Evaluate the quality of this approach:

Thought: {thought.get('thought', '')}
Data: {json.dumps(thought.get('data', {}), ensure_ascii=False)}

Rate this approach on a scale of 0-10 based on:
1. Feasibility (可行性)
2. Creativity (创新性)
3. Effectiveness (有效性)
4. Efficiency (效率)

Respond in JSON format:
{{
  "score": <0-10>,
  "reasoning": "..."
}}"""

        try:
            response = await unified_llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"score": "number", "reasoning": "string"},
                provider="claude",
                model="haiku-4.5",  # 使用快速模型
                temperature=0.3
            )

            return response.get("score", 5.0) / 10.0

        except Exception as e:
            logger.error(f"Evaluate thought error: {e}")
            return 0.5

    async def _reflection_execution(
        self,
        input_data: Dict[str, Any],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Self-Reflection (自我反思)

        执行 -> 反思 -> 改进 -> 再执行

        算法:
        1. 执行任务
        2. 自我评估结果
        3. 识别问题和改进点
        4. 重新执行
        5. 重复直到满意或达到最大迭代次数
        """
        iterations = []
        current_result = None

        for i in range(max_iterations):
            # 1. 执行任务
            if i == 0:
                result = await self._direct_execution(input_data)
            else:
                # 使用反思结果改进
                improved_input = {
                    **input_data,
                    "improvements": iterations[-1]["reflection"]["improvements"]
                }
                result = await self._direct_execution(improved_input)

            # 2. 自我反思
            reflection = await self._self_reflect(result, input_data)

            # 3. 记录迭代
            iterations.append({
                "iteration": i + 1,
                "result": result,
                "reflection": reflection
            })

            # 4. 检查是否满意
            if reflection.get("satisfied", False):
                current_result = result
                break

            current_result = result

        return {
            "iterations": iterations,
            "final_result": current_result,
            "num_iterations": len(iterations)
        }

    async def _self_reflect(
        self,
        result: Dict[str, Any],
        original_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """自我反思"""
        prompt = f"""Original task: {json.dumps(original_input, ensure_ascii=False)}

My result: {json.dumps(result, ensure_ascii=False)}

Please reflect on this result:
1. What did I do well?
2. What could be improved?
3. Are there any errors or issues?
4. Am I satisfied with this result?
5. If not, what specific improvements should I make?

Respond in JSON format:
{{
  "strengths": ["..."],
  "weaknesses": ["..."],
  "errors": ["..."],
  "satisfied": true/false,
  "improvements": ["..."]
}}"""

        try:
            response = await unified_llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={
                    "strengths": "array",
                    "weaknesses": "array",
                    "errors": "array",
                    "satisfied": "boolean",
                    "improvements": "array"
                },
                provider="claude",
                model="sonnet-4.5",
                temperature=0.5
            )

            return response

        except Exception as e:
            logger.error(f"Self-reflection error: {e}")
            return {"satisfied": True, "improvements": []}

    async def _direct_execution(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """直接执行 (子类实现)"""
        raise NotImplementedError("Subclass must implement _direct_execution")

    def _store_short_term_memory(self, data: Dict[str, Any]):
        """存储短期记忆"""
        self.short_term_memory.append({
            "timestamp": datetime.now().isoformat(),
            "data": data
        })

        # 限制短期记忆大小
        if len(self.short_term_memory) > 100:
            self.short_term_memory = self.short_term_memory[-100:]

    def _store_long_term_memory(self, input_data: Dict[str, Any], result: Dict[str, Any]):
        """存储长期记忆"""
        key = self._generate_memory_key(input_data)

        if key not in self.long_term_memory:
            self.long_term_memory[key] = []

        self.long_term_memory[key].append({
            "timestamp": datetime.now().isoformat(),
            "input": input_data,
            "result": result
        })

    def _generate_memory_key(self, data: Dict[str, Any]) -> str:
        """生成记忆键"""
        # 简单实现：使用任务类型作为键
        return data.get("task", "default")

    async def learn_tool(self, tool_name: str, tool_description: str, tool_function):
        """学习新工具"""
        self.tools[tool_name] = {
            "description": tool_description,
            "function": tool_function,
            "usage_count": 0,
            "success_count": 0
        }

        logger.info(f"Agent {self.config.name} learned new tool: {tool_name}")

    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """使用工具"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")

        tool = self.tools[tool_name]
        tool["usage_count"] += 1

        try:
            result = await tool["function"](**kwargs)
            tool["success_count"] += 1
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            raise

    def get_tool_statistics(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        stats = {}
        for tool_name, tool in self.tools.items():
            stats[tool_name] = {
                "usage_count": tool["usage_count"],
                "success_count": tool["success_count"],
                "success_rate": (
                    tool["success_count"] / tool["usage_count"]
                    if tool["usage_count"] > 0 else 0
                )
            }
        return stats

    async def send_message(self, to_agent: str, message: Dict[str, Any]):
        """发送消息给其他 Agent"""
        self.message_queue.append({
            "from": self.config.name,
            "to": to_agent,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    async def receive_messages(self) -> List[Dict[str, Any]]:
        """接收消息"""
        messages = [
            msg for msg in self.message_queue
            if msg["to"] == self.config.name
        ]

        # 清除已读消息
        self.message_queue = [
            msg for msg in self.message_queue
            if msg["to"] != self.config.name
        ]

        return messages

    def get_memory_summary(self) -> Dict[str, Any]:
        """获取记忆摘要"""
        return {
            "short_term_memory_size": len(self.short_term_memory),
            "long_term_memory_keys": list(self.long_term_memory.keys()),
            "total_experiences": sum(
                len(experiences)
                for experiences in self.long_term_memory.values()
            )
        }
